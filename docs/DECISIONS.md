# Decisions

Each real choice gets one short record that says what was decided and why. Every number tuned after it was seen gets a line here, and so does every change to the answer key after a model ran.

## The story

A residential installer's quality desk checks a technician's closeout photos against the job's design before the job closes and the warranties are registered. The alternatives were a load survey before an EV charger or a property manager's equipment audit, and the quality desk won because a missed mismatch there costs a callback, a failed inspection, or a denied warranty.

## The layout

Mockup C in a light theme won. The photo sits as a mounted print on a bright table with a faint dot grid, navy ink, and safety orange, and it looks unlike the other demos on the site.

## The photos

On 11/9 the photos became synthetic because a public demo shouldn't carry a real brand, a serial number, or somebody's house. generate/render.py draws 16 plates and 5 breaker close-ups from generate/plates.json and photographs them as 45 phone-like shots with an angle, glare, dim light, and grain. The answer key, the designs, and the job come from the same file. The key is exact by construction, and the verification page isn't needed. The page says the photos are synthetic, and a rendered plate is weaker proof than a real one even though the pipeline is the same for both. Each breaker that feeds a listed asset has its own close-up, and the tuning set includes a plate that prints both a minimum circuit ampacity and a largest breaker because those two values are the easiest to confuse.

## What the masks would cover on a real photo

Makers' names and logos, serial numbers, certification marks, installer and utility stickers, addresses, phone numbers, web addresses, patent numbers, barcodes, and QR codes are all masked. Model numbers stay readable because the read and the design check need them, and the page never names a maker. Each mask is a flat patch in the area's own color with a soft edge because blurred or pixelated text can sometimes be read back.

## The breaker checks

There are two breaker checks. One compares the design's breaker with the plate's maximum and the other compares the breaker photo with the design. A single check driven by the design alone would turn the condenser green when the design changed while the photo still showed the bigger breaker. With two checks an edit to the design moves the failure from the paperwork to the panel, and an engineer's first question has an answer.

## The sets and the split

The job on the page is drawn from the test plates, and every shot of every test plate is scored. The dev set is about five plates. The split is drawn by plate with seed 11 and fixed rules before any model runs. Dev takes one plate with both breaker values, never the one the job's cross-photo check needs most, one breaker close-up, never the highest rated, and up to three more plates at random.

## How a read is confirmed

A read is found when its exact value sits by its own label on a line the text recognition rated 0.5 or higher, or carries its own unit for the fields where a unit says enough. A value by another field's label of the same kind or by a label no field reads is away from its label. One character off counts only for model numbers and refrigerants of four characters or more because 25 against 35 is a different breaker. Words joined on one line count as found because the text recognition splits words at random, and a value pieced across two lines is only partly found.

The first real text recognition on 11/9 found 121 of the key's 175 values, and four changes brought it to 173. A unit that follows its number (HZ, PSIG, or AIC) isn't a label. A value's own unit decides before a label on another line. Each row follows the slant of its own line because an angled shot slants the top rows less than the bottom ones. Letters from other alphabets that look like Latin ones read as Latin because the text recognition returned MCA and MOCP in Cyrillic letters. The two values still missed are real misreads of a phase in dim light and a model's last character, and both go to a person.

## No verdict on a waiting read

A failing check turns its asset red only when every value it used is settled. Anything resting on a read that waits for a person keeps the asset blue. The scorer's decision bar comes from the same rule. A wrong verdict counts as caught only when the check waited for a person.

A read the AI couldn't make out is settled only by a correction. Accepting it would say the plate doesn't print the value, and the check would pass without anyone seeing it.

## The glare that goes to a person

The job's dryer is photographed in glare so that its model goes to a person. A mild glare hid nothing from the text recognition, and the dryer's shot now has a hot spot over the whole model number. A faint first and last character would have let a partial read be confirmed by its label and turned the person into a false fail. A test checks every planted outcome against the real text recognition.

## What the AI sees

The read gets the masked photo and the field schema and nothing else, and it never sees the design and can't read what it expects to find. The reply has no free-text field, the prompt forbids naming a maker, and the recorder replaces any word from under the masks with "[maker]" before a record is saved.

## The bars

Set on 11/9 before any read, the bars are field accuracy of 0.90 on test, zero wrong reads past the default line, and zero wrong verdicts that skip the person. The route is the cheapest model that clears every bar on dev, or the most accurate on dev when none does.

## The privacy scan without pixels

The build is standard library only and can't decode a JPEG. The scan reads each photo's markers instead, matches its hash to the masking log, checks the recognized text for anything under a mask, and checks every text file for the words from under the masks.

## The keys

The config names this project's own Keychain items, and a one-time copy brings over the keys an earlier project saved. The public repo doesn't depend on another project's names.

Claude is called through the Anthropic API like the other vendor and reads its key from the Keychain. On 11/9 no Anthropic key existed under either earlier name, and a first try through the `claude -p` command line never reached a read. An API key replaced that path because it calls every model the same way and prices every call from its tokens. The `claude -p` backend came out of the code on 11/10 because no recorded read went through it. A model that reads nothing on its first photo stops before anything is saved because that most likely means the photo isn't reaching it.

## The preview

The page was built and tested on drawn plates with a stand-in that answers from the key before the real photos were read. The preview says so on every screen, and the real build and the export refuse it.

## The code budget

The plan set about 3,300 lines of Python, and the build came in near 4,150 before the photo renderer and 4,600 with it. The plan expected real photos and had no renderer. The confirmation step and the privacy scan carry long docstrings that explain the method, the scripts for real photos stay for a client's photos, and the browser check came over from an earlier project. The JavaScript and the CSS came in well under their budgets. The Python stayed as it is on 11/10.

## Numbers tuned after they were seen

The prompt was never tuned. Claude Sonnet's dev round on 11/9 read 35 of the 36 values right with no wrong read, nothing past the line, and no missed verdict. The one miss was an honest unreadable on a breaker size the glare had nearly washed out, and it went to a person. A revision aimed at that one value could only trade a safe miss for a wrong read. The prompt froze after round 1 as written.

The confirmation step changed before any model ran. Four fixes came from the first real text recognition, and they're in the section on how a read is confirmed. They were checked against the key on every photo including the test photos because the text recognition is part of the photo stage and no model had read anything yet.

## Wording changed after the freeze

On 11/10 a docstring in engine/confirm.py and the note in config/fields.json were reworded. Neither changes what the model sees or how a read is confirmed, and evals/frozen.json keeps the old hashes in its history.

## Changes to the answer key after a model ran

None yet.
