"""Publish a workshop session to figshare as a mirror of the primary deposit.

Maintainer tool, and the counterpart to ``publish_zenodo.py``. The workshop's
data lives on UCLA Dataverse; when that archive's storage failed — metadata
resolving perfectly while every file download returned 404 — nobody who had not
already pulled the data could get it at all.

figshare is the mirror host because it is *fast*. Measured against this repo's
own link: figshare served ~6.6 MB/s where Zenodo managed ~0.6 MB/s, which is the
difference between a 22-minute download and a 4-hour one. For a room of
participants pulling ~9 GB during a workshop, that is the whole ballgame — a
mirror nobody can practically download from is not a backup.

``get_data.py`` reads figshare with **no changes at all**: a figshare DOI falls
through to pooch, which resolves it natively. Publish here, add the DOI to the
session's list in ``SESSIONS``, and fetches fail over automatically.

Files go up in exactly the layout ``get_data.py`` expects: every file in
``data/sessions/<session>/raw/`` individually, plus one singly-zipped bundle per
processed stage.

Usage::

    python scripts/publish_figshare.py --dry-run           # what would upload
    python scripts/publish_figshare.py                     # upload, leave a draft
    python scripts/publish_figshare.py --publish           # upload and publish
    python scripts/publish_figshare.py --article 12345678  # resume into a draft

Uploads **resume twice over**: a file already stored with a matching MD5 is
skipped entirely, and a file left half-sent is continued *part by part* rather
than restarted. figshare uploads in explicit byte-range parts, so an interrupted
784 MB push costs only the part in flight. A stored file that does *not* match
the local copy is deleted and re-sent — never initiated a second time, since
figshare allows duplicate names within an article and a mirror serving two
different ``minian_out.zip``s would be worse than no mirror.

Nothing is published unless you pass ``--publish``. Publishing is what mints the
DOI and what makes the files immutable, so the default leaves an editable draft
to inspect first.

The API token is read from ``.figshare_token`` or ``$FIGSHARE_TOKEN``; see
``.figshare_token.example``. It is never printed, not even in error messages.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

from _publish_common import retrying
from _publish_common import (DESCRIPTION_HTML, KEYWORDS, REPO_URL, TITLE_FMT,
                             UPLOAD_TIMEOUT, Progress, add_common_args, human,
                             load_token, md5, mirror_hint, plan)

API = "https://api.figshare.com/v2"
_TIMEOUT = 60  # control-plane calls; upload PUTs use UPLOAD_TIMEOUT

TOKEN_FILE = ".figshare_token"
TOKEN_ENV = "FIGSHARE_TOKEN"


def metadata(session: str, primary_doi: str | None, license_id: int,
             categories: list[int]) -> dict:
    """Article metadata in figshare's schema; the shared text lives in
    ``_publish_common`` so both archives stay word-identical."""
    refs = [REPO_URL]
    if primary_doi:
        refs.append(f"https://doi.org/{primary_doi}")
    return {
        "title": TITLE_FMT.format(session=session),
        "description": DESCRIPTION_HTML,
        "defined_type": "dataset",
        "tags": KEYWORDS,
        "categories": categories,
        "license": license_id,
        "references": refs,
    }


class Figshare:
    """The slice of the figshare v2 API this script needs."""

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"token {token}"

    # -- plumbing ----------------------------------------------------------
    def _call(self, method: str, path: str, **kw):
        r = self.session.request(method, f"{API}{path}", timeout=_TIMEOUT, **kw)
        self._raise(r)
        # Not every 2xx carries JSON: completing a file upload returns a bare
        # 202 Accepted, and parsing that as JSON crashes an otherwise-finished
        # multi-hundred-MB upload at the last step.
        try:
            return r.json() if r.content else {}
        except ValueError:
            return {}

    @staticmethod
    def _raise(r: requests.Response) -> None:
        """Turn an API error into a readable message, never echoing the token."""
        if r.ok:
            return
        detail = ""
        try:
            body = r.json()
            detail = body.get("message", "") or str(body)[:300]
        except ValueError:
            detail = r.text[:300]
        hint = ""
        if r.status_code in (401, 403):
            hint = ("\n  The token was rejected. Check .figshare_token holds a valid "
                    "personal token from https://figshare.com/account/applications")
        raise SystemExit(f"figshare API {r.status_code} on {r.request.method} "
                         f"{r.request.path_url}: {detail}{hint}")

    # -- lookups -----------------------------------------------------------
    def license_id(self, want: str = "CC BY 4.0") -> int:
        """Resolve a license name to figshare's numeric id.

        Looked up rather than hardcoded: the ids are account- and
        portal-dependent, and a wrong one fails only at publish time.
        """
        for lic in self._call("GET", "/licenses"):
            if want.lower().replace(" ", "") in lic["name"].lower().replace(" ", ""):
                return lic["value"]
        sys.exit(f"No license matching {want!r} on this account. Available: "
                 + ", ".join(l["name"] for l in self._call("GET", "/licenses")))

    def category_ids(self, want: str) -> list[int]:
        """Selectable category ids matching *want*.

        figshare's taxonomy has ~2180 entries, but only the leaves accept
        articles: the parent nodes carry ``is_selectable: false`` and creating an
        article against one fails with a 404 that reads like the category does
        not exist ("Not allowed to set category X"). Filter to selectable ones so
        a reasonable-looking name cannot silently pick an unusable node.
        """
        cats = [c for c in self._call("GET", "/categories") if c.get("is_selectable")]
        exact = [c for c in cats if c["title"].lower() == want.lower()]
        hits = exact or [c for c in cats if want.lower() in c["title"].lower()]
        if hits:
            print(f"  category: {hits[0]['title']} (id {hits[0]['id']})")
        return [c["id"] for c in hits[:1]]

    # -- articles ----------------------------------------------------------
    def create_article(self, meta: dict) -> int:
        loc = self._call("POST", "/account/articles", json=meta)["location"]
        return int(loc.rstrip("/").rsplit("/", 1)[-1])

    def article(self, article_id: int) -> dict:
        return self._call("GET", f"/account/articles/{article_id}")

    def update_article(self, article_id: int, meta: dict) -> None:
        self._call("PUT", f"/account/articles/{article_id}", json=meta)

    def files(self, article_id: int) -> list[dict]:
        """Every file in the article — explicitly unpaginated.

        figshare defaults this endpoint to 10 results. Taking that default is
        catastrophic here rather than merely incomplete: the resume filter reads
        this list, so from the 11th file on every restart sees "not uploaded
        yet", re-initiates, and — since figshare permits same-named files in one
        article — leaves duplicates behind. A deposit holding several different
        blobs under one name is worse than one that is simply missing it.
        """
        return self._call("GET", f"/account/articles/{article_id}/files",
                          params={"page_size": 1000})

    def delete_file(self, article_id: int, file_id: int) -> None:
        self._call("DELETE", f"/account/articles/{article_id}/files/{file_id}")

    def publish(self, article_id: int) -> dict:
        return self._call("POST", f"/account/articles/{article_id}/publish")

    # -- uploads -----------------------------------------------------------
    def ensure_file(self, article_id: int, name: str, path: Path,
                    existing: dict | None) -> int:
        """A file id it is safe to upload *path* into, replacing stale state.

        figshare does not enforce unique names within an article, so initiating
        a second file over a stale one would leave both — and a mirror serving
        two different files under one name is worse than no mirror. Anything
        that cannot be *continued* (already-complete file, or a half-sent one
        whose declared size no longer matches the local file — e.g. a rebuilt
        bundle) is deleted before a fresh initiation.
        """
        if existing:
            if existing.get("status") == "available" or \
                    int(existing.get("size") or 0) != path.stat().st_size:
                why = ("does not match the local copy"
                       if existing.get("status") == "available"
                       else "was initiated for a different size")
                print(f"       {name}: stored file {why} - deleting and re-sending")
                self.delete_file(article_id, existing["id"])
            else:
                return existing["id"]  # half-sent, same size: continue its parts
        body = {"name": name, "md5": md5(path), "size": path.stat().st_size}
        loc = self._call("POST", f"/account/articles/{article_id}/files",
                         json=body)["location"]
        return int(loc.rstrip("/").rsplit("/", 1)[-1])

    def upload(self, article_id: int, file_id: int, path: Path, label: str) -> None:
        """Send *path* part by part, skipping parts figshare already holds.

        figshare hands back an explicit part list with a status per part, which
        is what makes real resume possible: an interrupted multi-hundred-MB file
        continues from the part it stopped on instead of starting over.
        """
        info = self._call("GET", f"/account/articles/{article_id}/files/{file_id}")
        upload_url = info["upload_url"]
        # The upload service is a different, token-bearing host — module-level
        # requests (not self.session) is deliberate here; only the error check
        # routes through _raise.
        r = requests.get(upload_url, timeout=_TIMEOUT)
        self._raise(r)
        parts = r.json()["parts"]

        pending = [p for p in parts if p.get("status") != "COMPLETE"]
        already = sum(p["endOffset"] - p["startOffset"] + 1
                      for p in parts if p.get("status") == "COMPLETE")
        if already:
            print(f"       {label}: resuming, {human(already)} already stored")

        total = path.stat().st_size
        done = already
        try:
            for part in pending:
                start, end = part["startOffset"], part["endOffset"]
                body = Progress(path, label, offset=start, limit=end - start + 1,
                                done=done, total=total)
                try:
                    r = requests.put(f"{upload_url}/{part['partNo']}", data=body,
                                     timeout=UPLOAD_TIMEOUT)
                    done = body.done
                finally:
                    body.close()
                self._raise(r)
        finally:
            Progress.clear()

        # Completing is what moves the file from 'created' to 'available'; it
        # also makes figshare verify the MD5 we declared up front.
        self._call("POST", f"/account/articles/{article_id}/files/{file_id}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap)
    ap.add_argument("--article", type=int,
                    help="resume into an existing draft article id")
    ap.add_argument("--category", default="Behavioural neuroscience",
                    help="figshare category to file it under (required to publish). "
                         "Must be a selectable leaf of figshare's taxonomy, not a "
                         "parent heading like 'Neurosciences'")
    ap.add_argument("--license", default="CC BY 4.0", help="license name")
    args = ap.parse_args()

    items = plan(args)
    if items is None:  # --dry-run
        return 0

    api = Figshare(load_token(TOKEN_FILE, TOKEN_ENV))
    license_id = api.license_id(args.license)
    categories = api.category_ids(args.category)
    if not categories:
        print(f"  NOTE no category matching {args.category!r}; figshare will refuse "
              f"to publish until one is set (the draft is still fine).")
    meta = metadata(args.session, args.primary_doi or None, license_id, categories)

    if args.article:
        api.article(args.article)  # 404s loudly if it is not ours
        article_id = args.article
        api.update_article(article_id, meta)
        print(f"\nResuming draft article {article_id} (metadata refreshed)")
    else:
        article_id = api.create_article(meta)
        print(f"\nCreated draft article {article_id}")

    # Resume filter: a file stored complete whose MD5 matches is skipped.
    # An empty computed_md5 (figshare fills it in asynchronously) is treated as
    # unverifiable and re-sent — wasteful in the rare race, never wrong.
    have = {f["name"]: f for f in api.files(article_id)}
    todo = []
    for name, path in items:
        existing = have.get(name)
        if existing and existing.get("status") == "available" \
                and existing.get("computed_md5") == md5(path):
            continue
        todo.append((name, path, existing))
    skipped = len(items) - len(todo)
    if skipped:
        print(f"  {skipped} file(s) already stored and matching — skipping.")
    if todo:
        print(f"  uploading {len(todo)} file(s), "
              f"{human(sum(p.stat().st_size for _, p, _ in todo))}")

    for i, (name, path, existing) in enumerate(todo, 1):
        label = f"[{i}/{len(todo)}] {name}"
        file_id = api.ensure_file(article_id, name, path, existing)
        # On retry the part list is re-read, so completed parts are not re-sent.
        retrying(lambda: api.upload(article_id, file_id, path, label), label)
        print(f"       {label} done ({human(path.stat().st_size)})")

    if not args.publish:
        print(f"\nDraft ready but NOT published:\n"
              f"    https://figshare.com/account/articles/{article_id}\n"
              f"Review it, then publish with:\n"
              f"    python scripts/publish_figshare.py --session {args.session} "
              f"--article {article_id} --publish")
        return 0

    api.publish(article_id)
    pub = api.article(article_id)
    doi = pub.get("doi", "")
    print(f"\nPublished: {pub.get('url_public_html', '')}")
    print(f"  DOI: {doi}")
    print(mirror_hint(args.session, args.primary_doi or None, doi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
