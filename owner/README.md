# The owner's runs

Everything here runs on the owner's Mac in a normal terminal from the build folder. Nothing in the build calls a model or the network, and these are the only steps that read the raw photos, run the text recognition, mask a photo, or call a model. Each prints what it did and the next step, and each is safe to run again.

## The order

1. `bash owner/bootstrap.sh` makes `.venv/` with Homebrew's Python, installs Pillow, pillow-heif and the Vision bindings, puts the fonts in place, and runs two self-tests on images they draw themselves. It takes about three minutes the first time.
2. `bash owner/ocr.sh` reads the text on every photo with the Mac's own Vision framework and runs the privacy scan. It takes about a minute. The photos are synthetic, and `generate/render.py` draws them along with the answer key.
3. `bash owner/keys.sh` saves the two keys once from the clipboard or from another project's items. Then `bash owner/run.sh 1` is the tuning round. A dry run with the stand-in comes first, and then the default model reads the tuning photos and the scores are written. It takes about five minutes.
4. `bash owner/run.sh 2` runs once the prompt is ready, and it takes about fifteen minutes unattended. It runs the tuning round again if the prompt changed, and then it runs every model on every photo and scores them. The real build and its screenshots follow once `config/names.json` is in, and until then it says they're waiting.
5. `bash owner/screenshots.sh` builds the page and shoots it in headless Chrome for each review round.

## Real photos

Real photos take three more steps before the text is read. `bash owner/prepare.sh` turns each photo upright, drops its metadata and drafts its values, `bash owner/verify.sh` opens the page where a person confirms every value and sets every mask, and `bash owner/prepare.sh --mask` applies the masks and deletes the unmasked copies.

## The keys

The models are called through each vendor's API with keys saved in the macOS Keychain under `field-inspector-anthropic` and `field-inspector-openai`. `bash owner/keys.sh` saves each one from the clipboard or copies the ones another project already saved. The scripts read them with the `security` command and hand them straight to the request, and they never print a key or write one to a file.

## What the scripts keep private

The raw photos stay outside the repo, and the unmasked copies and the draft read are deleted once the masks are applied. The words that were under the masks go to `owner/private/` where git never sees them, and the recorder and the scans use them to make sure no maker's name reaches a recording or the repo. Screenshots and logs go to `owner/out/` where git never sees them either.
