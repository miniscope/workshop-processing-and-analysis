"""Publish a workshop session to Zenodo as a mirror of the primary deposit.

Maintainer tool, and the counterpart to ``publish_figshare.py``. The workshop's
data lives on UCLA Dataverse, and when that archive's storage went down —
metadata resolving perfectly while every single file download returned 404 —
nobody who had not already pulled the data could get it at all. A second copy on
an unrelated host removes that single point of failure, and ``get_data.py``
already knows how to read one: list the Zenodo DOI in ``SESSIONS`` next to the
Dataverse one and it fails over automatically.

**Prefer figshare for the workshop mirror.** Measured against this repo's link,
Zenodo served ~0.6 MB/s against figshare's ~6.6 MB/s — a ~4-hour download versus
~22 minutes for the full session. Zenodo is worth having as a preservation copy
(CERN-backed, stronger long-term guarantees than a commercial host), but a room
of participants should be pulling from the faster mirror. See
``publish_figshare.py``.

This script uploads a session in **exactly the layout ``get_data.py`` expects**,
so no reader-side change is needed:

* every file in ``data/sessions/<session>/raw/`` as an individual file, and
* one zip per processed stage (``minian_out.zip`` / ``deconv_out.zip`` /
  ``eztrack_out.zip``), taken from ``data/.cache/<session>/`` when it is there
  and built from the extracted stage dir when it is not.

Usage::

    python scripts/publish_zenodo.py --dry-run          # what would upload, no network
    python scripts/publish_zenodo.py --sandbox          # rehearse on sandbox.zenodo.org
    python scripts/publish_zenodo.py                    # upload to Zenodo, leave a draft
    python scripts/publish_zenodo.py --publish          # upload and publish (mints the DOI)
    python scripts/publish_zenodo.py --deposition 12345 # resume into an existing draft

Uploads **resume** at file granularity: anything already in the deposit with a
matching MD5 is skipped, so an interrupted push re-sends only the file that was
in flight. (Zenodo registers a file only once its PUT completes, so a part-way
file is not partially credited — unlike figshare, which resumes part by part.)

Nothing is published unless you pass ``--publish``. A draft can be inspected in
the browser, corrected, and re-uploaded into; a published record cannot have its
files changed, only superseded by a new version. Publishing is also the step that
mints the DOI, which is the thing you paste into ``SESSIONS``.

The API token is read from ``.zenodo_token`` (``.zenodo_token.sandbox`` with
``--sandbox``), or from ``$ZENODO_TOKEN`` / ``$ZENODO_SANDBOX_TOKEN``. See
``.zenodo_token.example`` for how to create one and which scopes it needs. The
token is never printed, not even in error messages.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

import requests

from _publish_common import (DESCRIPTION_HTML, KEYWORDS, REPO_URL, TITLE_FMT,
                             UPLOAD_TIMEOUT, Progress, add_common_args, human,
                             load_token, md5, mirror_hint, plan)

_TIMEOUT = 60  # control-plane calls; upload PUTs use UPLOAD_TIMEOUT

# Zenodo and its sandbox are separate sites with separate accounts and separate
# tokens. Rehearsing on the sandbox is advisable before a multi-GB push. The
# sandbox has no template of its own — .zenodo_token.example covers both.
HOSTS = {
    False: ("https://zenodo.org", ".zenodo_token", "ZENODO_TOKEN"),
    True: ("https://sandbox.zenodo.org", ".zenodo_token.sandbox", "ZENODO_SANDBOX_TOKEN"),
}
TOKEN_EXAMPLE = ".zenodo_token.example"


def metadata(session: str, doi_primary: str | None) -> dict:
    """Deposit metadata in Zenodo's schema; the shared text lives in
    ``_publish_common`` so both archives stay word-identical.

    When the primary DOI is known it is recorded as ``isIdenticalTo``, so the two
    deposits are visibly the same data rather than two unexplained copies.
    """
    related = [{"identifier": REPO_URL, "relation": "isSupplementTo", "scheme": "url"}]
    if doi_primary:
        related.append({"identifier": doi_primary, "relation": "isIdenticalTo",
                        "scheme": "doi"})
    return {
        "title": TITLE_FMT.format(session=session),
        "upload_type": "dataset",
        "description": DESCRIPTION_HTML,
        "creators": [
            {"name": "Aharoni, Daniel",
             "affiliation": "University of California, Los Angeles"},
        ],
        "license": "cc-by-4.0",
        "keywords": KEYWORDS,
        "related_identifiers": related,
    }


class Zenodo:
    """The slice of the Zenodo deposit API this script needs."""

    def __init__(self, token: str, sandbox: bool):
        self.base = f"{HOSTS[sandbox][0]}/api"
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"

    def _call(self, method: str, path: str, **kw):
        r = self.session.request(method, f"{self.base}{path}", timeout=_TIMEOUT, **kw)
        self._raise(r)
        return r.json() if r.content else {}

    @staticmethod
    def _raise(r: requests.Response) -> None:
        """Turn an API error into a readable message, never echoing the token."""
        if r.ok:
            return
        detail = ""
        try:
            body = r.json()
            detail = body.get("message", "")
            for err in body.get("errors", []):
                detail += f"\n    {err.get('field', '?')}: {err.get('message', '')}"
        except ValueError:
            detail = r.text[:300]
        hint = ""
        if r.status_code in (401, 403):
            hint = ("\n  The token was rejected. Check it is for this site "
                    "(sandbox and production tokens are not interchangeable) and "
                    "that it has the deposit:write and deposit:actions scopes.")
        raise SystemExit(f"Zenodo API {r.status_code} on {r.request.method} "
                         f"{r.request.path_url}: {detail}{hint}")

    def create(self) -> dict:
        return self._call("POST", "/deposit/depositions", json={})

    def get(self, dep_id: int) -> dict:
        return self._call("GET", f"/deposit/depositions/{dep_id}")

    def existing_files(self, dep_id: int) -> dict[str, str]:
        """``{filename: md5}`` already in the deposit, for resume."""
        files = self._call("GET", f"/deposit/depositions/{dep_id}/files")
        return {f["filename"]: str(f.get("checksum", "")).split(":", 1)[-1]
                for f in files}

    def upload(self, bucket: str, name: str, path: Path, label: str) -> None:
        """PUT one file into the deposit's bucket, verifying the server's MD5."""
        body = Progress(path, label)
        try:
            r = self.session.put(f"{bucket}/{quote(name)}", data=body,
                                 timeout=UPLOAD_TIMEOUT)
        finally:
            body.close()
            Progress.clear()
        self._raise(r)
        got = str(r.json().get("checksum", "")).split(":", 1)[-1]
        if not got:
            print(f"       NOTE Zenodo returned no checksum for {name}; "
                  f"transfer not verified.")
        elif got != md5(path):
            raise SystemExit(f"checksum mismatch after uploading {name}: "
                             f"Zenodo stored {got}, local file is {md5(path)}")

    def set_metadata(self, dep_id: int, meta: dict) -> dict:
        return self._call("PUT", f"/deposit/depositions/{dep_id}",
                          json={"metadata": meta})

    def publish(self, dep_id: int) -> dict:
        return self._call("POST", f"/deposit/depositions/{dep_id}/actions/publish")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap)
    ap.add_argument("--sandbox", action="store_true",
                    help="upload to sandbox.zenodo.org instead — rehearse here first")
    ap.add_argument("--deposition", type=int,
                    help="resume into an existing draft deposition id instead of "
                         "creating a new one")
    args = ap.parse_args()

    items = plan(args)
    if items is None:  # --dry-run
        return 0

    host, token_file, token_env = HOSTS[args.sandbox]
    api = Zenodo(load_token(token_file, token_env, example=TOKEN_EXAMPLE),
                 args.sandbox)

    if args.deposition:
        dep = api.get(args.deposition)
        print(f"\nResuming draft {dep['id']} on {host}")
    else:
        dep = api.create()
        print(f"\nCreated draft {dep['id']} on {host}")
    dep_id, bucket = dep["id"], dep["links"]["bucket"]

    have = api.existing_files(dep_id)
    # Hash only files the deposit already names — on a fresh draft that is
    # none of them, not a full pass over 9 GB whose result is discarded.
    todo = [(n, p) for n, p in items if n not in have or have[n] != md5(p)]
    skipped = len(items) - len(todo)
    if skipped:
        print(f"  {skipped} file(s) already uploaded and matching — skipping.")
    if todo:
        print(f"  uploading {len(todo)} file(s), "
              f"{human(sum(p.stat().st_size for _, p in todo))}")
    for i, (name, path) in enumerate(todo, 1):
        api.upload(bucket, name, path, label=f"[{i}/{len(todo)}] {name}")
        print(f"       [{i}/{len(todo)}] {name} done ({human(path.stat().st_size)})")

    api.set_metadata(dep_id, metadata(args.session, args.primary_doi or None))
    print("  metadata set.")

    if not args.publish:
        print(f"\nDraft ready but NOT published: {host}/uploads/{dep_id}\n"
              f"Review it in the browser, then either publish there or re-run with:\n"
              f"    python scripts/publish_zenodo.py --session {args.session} "
              f"--deposition {dep_id} --publish")
        return 0

    rec = api.publish(dep_id)
    doi = rec.get("doi") or rec.get("metadata", {}).get("prereserve_doi", {}).get("doi", "")
    concept = rec.get("conceptdoi", "")
    print(f"\nPublished: {rec.get('links', {}).get('record_html', '')}")
    print(f"  version DOI: {doi}")
    if concept:
        print(f"  concept DOI: {concept}  (resolves to the latest version)")
    print(mirror_hint(args.session, args.primary_doi or None, concept or doi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
