# Field Inspector: every visible word

Each `## key` starts an entry and the text under it is its value. The build fills `{name}` fields, the names come from `config/names.json`, and keys starting with `ui.` go to the page's script. A table entry is written one row per line as a name, an equals sign, and a label. Each paragraph sits on one line because the copy lint reads one line at a time.

## page.title
Field Inspector

## page.subtitle
{installer}

## page.description
A technician's nameplate photos go in, AI reads every plate, the photo's own text confirms each value, code checks the values against the job's design and across photos, and anything uncertain or failing goes to a person.

## page.preview
This preview uses drawn plates and a stand-in for the AI and is never published

## page.preview_short
Preview

## page.footer
The photos are synthetic, and the installer, the job, its design, and the people are made up for this demo.

## page.footer_preview
This preview runs on drawn plates and a stand-in that answers from the answer key, and nothing on it is a result.

## page.by
Built by Ryan Sansbury

## page.code
Code

## page.noscript
The job needs JavaScript to open, and How it works below reads fine without it.

## ui.top.job
Job {number}

## ui.top.kind
Whole-home system replacement

## ui.top.by
{technician} on {weekday}

## page.skip
Skip to the checks

## ui.state
- pass = passes every check
- fail = fails a check
- person = waits for a person

## top.model
Recorded reads

## top.log
Audit log

## top.how
How it works

## top.tour
Take the tour

## top.back
Back to the job

## strip.label
The job's photos

## ui.weekdays
- 0 = Sunday
- 1 = Monday
- 2 = Tuesday
- 3 = Wednesday
- 4 = Thursday
- 5 = Friday
- 6 = Saturday

## ui.count.pass
{n} pass

## ui.count.fail
{n} fail

## ui.count.person
{n} for a person

## ui.kinds
- heat pump = Outdoor heat pump
- condenser = Outdoor condenser
- air handler = Air handler
- furnace = Furnace
- water heater = Water heater
- panel = Electrical panel
- breaker = Breaker close-up
- range = Range
- dryer = Dryer
- washer = Washer
- dishwasher = Dishwasher
- refrigerator = Refrigerator
- microwave = Microwave
- garage door opener = Garage door opener
- charger = Charger
- other = Equipment

## ui.places
- side_yard = side yard
- attic = attic
- garage = garage
- laundry = laundry room
- kitchen = kitchen
- basement = basement
- utility = utility closet
- hall = hall closet

## ui.fields
- model = Model
- volts = Volts
- phase = Phase
- amps = Amps
- mca = Min. circuit
- max_breaker = Max breaker
- capacity = Capacity
- refrigerant = Refrigerant
- breaker = Breaker

## ui.shots
- straight = shot straight on
- angled = shot at an angle
- glare = shot in glare
- low light = shot in low light

## ui.stage.caption
{kind} in the {place}

## ui.stage.count
photo {n} of {total}

## ui.stage.note
Read in {seconds} seconds with {found} of {total} values found on the photo

## ui.stage.alt
Nameplate of the {kind} {shot}

## ui.zoom.fit
Fit

## ui.zoom.full
Full size

## ui.zoom.words
Show the photo's own words

## ui.zoom.words_off
Hide the photo's own words

## ui.inset.title
Its circuit in the breaker photo

## ui.inset.over
{installed} A on its circuit against a {max} A maximum

## ui.inset.ok
{installed} A on its circuit

## ui.inset.alt
Close-up of the breaker on the {kind}'s circuit

## ui.insp.reads
What it read

## ui.insp.line
The confidence line

## ui.insp.checks
The checks

## ui.insp.queue
For a person

## ui.insp.queue_empty
Nothing waits for a person right now, and every check on the job stands on reads the photos confirmed.

## ui.insp.absent
The AI says the plate doesn't print it

## ui.insp.reset
Reset the job

## ui.levels
- found = Found on the photo
- partial = Partly found
- missing = Not found
- person = Settled by a person

## ui.why
- label = by its label
- unit = with its unit
- box = where the AI pointed
- one_off = one off from the photo's {seen}
- away = away from its label
- split = across two lines
- low = on a line the recognizer doubted
- ambiguous = twice where the AI pointed
- none = not in the photo's text
- unreadable = the AI couldn't read it
- unparsed = not a value of its kind
- absent = the AI says it isn't printed
- approx = an approximate box the AI drew
- held = not a value of its kind

## ui.line.positions
- missing = Not found
- partial = Partly found
- all = Found

## ui.line.note
Shaded levels send {sent} of {reads} reads to a person.

## ui.rules
- model = Model matches the design
- capacity = Capacity matches the design
- refrigerant = Refrigerant matches the design
- volts = Volts fit the design's circuit
- breaker_max = Breaker within the plate's maximum
- breaker_min = Breaker covers the plate's minimum
- panel = Breaker photo matches the design
- readable = The photo can be read

## ui.status
- pass = Pass
- fail = Fail
- review = For a person
- unknown = Waits on a read
- skipped = Skipped

## ui.check.design
Design

## ui.check.plate
Plate

## ui.check.photo
Breaker photo

## ui.check.waits
This waits until a person settles the read.

## ui.check.why
- equal = The plate matches the design.
- approved = The plate shows an approved equal.
- approved_by_person = A person approved the plate's model as an equal.
- wrong_unit = A person called it the wrong unit.
- one_off = One character off, and a person decides.
- differs = The plate and the design differ.
- fits = The plate's rating fits the design's voltage.
- volts = The plate's rating doesn't fit the design's voltage.
- phase = The plate's phase differs from the design's.
- within = Within the limit.
- over = The design's breaker is bigger than the plate allows.
- under = The design's breaker is smaller than the plate needs.
- no_read = The check has no value to read yet.
- read = The AI read at least one value.
- nothing_read = Nothing read, and the photo needs a new shot.
- no_breaker_photo = There's no breaker photo for this circuit.
- absent_confirmed = A person confirmed the plate doesn't print it.

## ui.queue.read
{field} on the {asset}

## ui.queue.check
{asset} model

## ui.queue.accept
Accept

## ui.queue.correct
Correct

## ui.queue.save
Save

## ui.queue.approved
Approved equal

## ui.queue.wrong
Wrong unit

## ui.queue.placeholder
What the photo shows

## ui.queue.readas
{value} · {why}

## ui.queue.noread
{why}

## ui.queue.design
Reads {plate} where the design says {design}

## ui.model.note
Switching models starts the person's decisions over.

## ui.log.title
Audit log

## ui.log.close
Close

## ui.log.empty
The log fills as the job is worked.

## ui.log.read
{model} read {n} photos on {date}.

## ui.log.checks
The checks ran with {pass} passing, {fail} failing, and {person} waiting for a person.

## ui.log.accept
{reviewer} accepted the {field} read of {value} on the {asset}.

## ui.log.absent
{reviewer} confirmed the {asset}'s plate doesn't print the {field}.

## ui.log.correct
{reviewer} corrected the {field} on the {asset} from {before} to {after}.

## ui.log.typed
{reviewer} typed in {after} for the {field} on the {asset}.

## ui.log.approved
{reviewer} approved the {asset}'s {value} as an equal to the design's {design}.

## ui.log.wrong
{reviewer} called the {asset}'s {value} the wrong unit.

## ui.log.design
The design's {field} for the {asset} changed from {before} to {after}.

## ui.log.line
The confidence line moved, and {sent} reads go to a person.

## ui.log.model
The page switched to the reads {model} recorded.

## ui.log.reset
The job was reset to its first state.

## ui.log.who
- ai = The AI
- code = The checks
- person = {reviewer}

## ui.tabs
- strip = Photos
- stage = Photo
- insp = Checks

## ui.present.step
Step {n} of {total}

## ui.present.back
Back

## ui.present.next
Next

## ui.present.done
Done

## ui.present.close
Close the tour

## ui.present.titles
- 1 = The job opens finished
- 2 = One photo and its receipts
- 3 = The catch across two photos
- 4 = How sure each read is
- 5 = The confidence line
- 6 = The person's queue
- 7 = The design is code
- 8 = The models side by side
- 9 = Every action in the log
- 10 = How it was measured

## ui.present.texts
- 1 = A technician photographed every nameplate on the job, and the page opens with each asset already read, confirmed, and checked against the design. The red ones failed a check, and the blue ones wait for a person to look at them.
- 2 = Every value the AI read is boxed where the photo's own text found it. A dashed box means the photo's text missed the value and the AI guessed where.
- 3 = The plate allows a breaker no bigger than its own maximum, and the design put a bigger one on this circuit. The breaker photo shows that bigger breaker already installed in the panel, and the check fails across both of the photos.
- 4 = Each read is found on the photo by its label, partly found, or not found, and that level decides what a person sees before any verdict is allowed to stand on it.
- 5 = Move the line and more or fewer reads go to a person, and the counts follow.
- 6 = The person accepts a read, types what the photo really shows, or decides whether a model one character off is an approved equal, and every check reruns.
- 7 = Change a value in the design and the checks rerun in the page as the same code the scores use, and the parity tests prove the two always agree on every case.
- 8 = Three models read the same photos, and the page switches between their recorded reads with every check and count recomputed on the spot.
- 9 = The log lists what the AI read, what the checks found, and every decision a person made along with the value it replaced and the time they made it.
- 10 = How it works shows the pipeline, the privacy steps, the scoreboard by field and by shot, the errors that got past the line, the models compared, and the code.

## ui.code.loading
Loading the code

## ui.code.files
Files

## how.title
How it works

## how.intro
A technician photographs every nameplate on an install, and this page checks those photos the way a quality desk would before the job closes out. AI reads each plate, the photo's own text confirms each value, code checks every value against the design and across photos, and a person sees only what's uncertain or failing and settles each one in the queue.

## how.map.title
What's AI, what's code, and what's a person

## how.map
- read = AI | Reading each plate's fields from the photo | Scored field by field against the answer key
- words = Code | Finding the words on the photo and their boxes on the owner's Mac | Its words are stored with each photo
- confirm = Code | Confirming each read by the photo's own text near its label | Found, partly found, or not found
- checks = Code | Comparing each value with the design and with the other photos | Unit tests and parity tests against the page's copy of the rules
- route = Code | Sending reads to a person from the confidence line | Scored as errors caught against reads sent
- person = A person | Settling what's uncertain and deciding what's failing | The queue and the audit log

## how.map.cols
- who = Who
- what = What it does
- check = How it's checked

## how.fields.cols
- field = Field
- shot = Shot
- values = Values in the key

## how.runs.cols
- photo = Photo
- model = Model
- date = Recorded
- tokens = Tokens in and out
- cost = Cost
- seconds = Seconds

## ui.check.none
not read

## how.pipeline.title
From the camera to the person

## how.pipeline
- shoot = Code draws each plate and photographs it straight on and then once or twice more at an angle, in glare, or in dim light.
- strip = Every photo is saved with no metadata at all, and flat patches stand where a maker's name and a serial would be masked.
- mask = The answer key comes from the same file that drew the plates, and every value in it is exactly what its photo shows.
- words = The Mac's own text recognition finds every word on the masked photo with its box, and nothing leaves the machine.
- read = Each model reads the photo once into fixed fields with each value's label and a rough box, and it never sees the design.
- confirm = Code looks for each value among the recognized words and checks that it sits by its own label.
- checks = Code runs the installer's rules on every value and across photos, and anything uncertain or failing goes to a person.

## how.privacy.title
The photos and their privacy

## how.privacy
Every plate is made up, and no real maker, serial, or place appears on any photo. Scripts already in the code would rebuild a client's real photos from their pixels with no metadata, and a person would confirm every mask and key value before any model saw them.

## how.privacy.scan
The scan runs in the build and again on the public copy of the repo, and it checked {photos} published image files and found {problems} problems. It looks for any metadata, any photo missing from the masking log, and any word the text recognition can still read under a mask.

## how.confirm.title
How a read gets confirmed

## how.confirm
A read is found when its exact value is in the photo's own words by its label or carries its own unit where a unit says enough. A value by another field's label never counts, and a minimum circuit ampacity read as the largest breaker goes to a person. A model number one character off is only partly found. Case, spacing, and units are evened out before the comparison, and an O never turns into a 0.

## how.rules.title
The checks in plain sentences

## how.rules
These are the installer's own design rules, and they're kept as data and run by the same code in the build and in this page. They aren't an inspection or an electrician's sign-off on the work. Edit a design value beside any check on the job and it reruns on the spot.

## how.rules.list
- model = The model on the plate matches the design or one of its approved equals.
- capacity = The capacity on the plate matches the design's.
- refrigerant = The refrigerant on the plate matches the design's.
- volts = Each design voltage fits a rating on the plate, and so does the phase.
- breaker_max = The design's breaker is no bigger than the largest the plate allows.
- breaker_min = The design's breaker is at least the plate's minimum circuit ampacity.
- panel = The breaker photographed on the circuit is the one the design calls for.
- readable = The AI could read at least one value from the photo.

## how.scores.title
The scoreboard

## how.scores
Each model got the same photos and saw none of the test photos until the prompt was frozen, and no AI graded its own reading.

## how.scores.preview
These preview scores belong to a stand-in that answers from the key and prove only the wiring.

## how.scores.cols
- model = Model
- accuracy = Fields right
- past = Wrong reads past the line
- missed = Wrong verdicts that skipped the person
- share = Reads sent to a person
- cost = Cost per photo
- seconds = Seconds per photo

## how.fields.title
By field and by shot

## how.line.title
Errors past the line and the person's load

## how.line
A wrong read is dangerous only when the photo seemed to confirm it, and the table counts those at each position of the line.

## how.line.positions
- missing = Only what's not found
- partial = Partly found and not found
- all = Every read

## how.line.cols
- position = Line at
- sent = Sent to a person
- caught = Wrong reads caught
- past = Wrong reads past the line

## how.models.route
The page opens on {model} because it's the {reason}.

## how.models.reasons
- cheapest_clearing = cheapest model that cleared every bar on the tuning photos
- most_accurate_on_dev = most accurate model on the tuning photos when none cleared every bar

## how.models.rule
The rule was set before any model read a photo, and it never looks at the test photos because a lucky test score shouldn't be what picks the model.

## how.runs.title
The recorded reads

## how.runs
Each read was recorded once on the owner's machine with its prompt, tokens, cost, and time, and this page only replays them.

## how.runs.show
Show all {n} recorded reads

## how.client.title
What checking your own photos would take

## how.client
The pattern carries to any plate, form, or label your technicians photograph. It takes a few hundred of your photos with their answers confirmed by your quality desk, your design rules written as data, a run of the models on photos they never saw, and a line set where your team is comfortable. After that your people see only what the photos can't settle, and the rest of the work moves on its own.

## how.limits.title
What it can't do

## how.limits
It reads what the photo shows, and a plate behind a bracket or under glare goes to a person. It checks the installer's rules and nothing else, and it isn't an inspection. It isn't production software. The page replays reads recorded in advance and can't read a new photo.

## how.code.title
The code

## how.code
Five files carry most of the idea, and the whole project is below them.

## how.code.featured
- engine/confirm.py = The confirmation step
- engine/rules.py = The checks
- prompts/read.md = The read prompt and its fields
- generate/render.py = The synthetic photos
- evals/score.py = The scorer
