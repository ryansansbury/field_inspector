"""The read's plumbing with no network: every backend's request carries the photo, usage turns into cost, retries back
off, the reply check holds what it should, the stand-in round-trips, a model that reads nothing on its first photo
stops, and a maker's word never reaches a record."""
import base64
import json
import tempfile
import unittest
from pathlib import Path

from agents import inputs, llm, validate
from engine import privacy
from owner import stand_in

PHOTO = {"media_type": "image/jpeg", "bytes": b"\xff\xd8 a tiny photo \xff\xd9"}
FIELDS = inputs.fields()
SCRATCH = inputs.HERE.joinpath(".cache", "tmp")


def anthropic_reply(text):
    return json.dumps({"model": "claude-sonnet-5-5", "content": [{"type": "text", "text": text}],
                       "usage": {"input_tokens": 2000, "output_tokens": 500}, "stop_reason": "end_turn"}).encode()


class Bodies(unittest.TestCase):
    def test_anthropic_sends_the_photo_before_the_text(self):
        b = llm.AnthropicAPI("k", "claude-sonnet-5-5")
        body = json.loads(b.request("system", "user", PHOTO)[1])
        content = body["messages"][0]["content"]
        self.assertEqual([c["type"] for c in content], ["image", "text"])
        self.assertEqual(base64.b64decode(content[0]["source"]["data"]), PHOTO["bytes"])
        self.assertEqual(body["system"], "system")

    def test_openai_sends_a_data_url_at_high_detail(self):
        b = llm.OpenAICompatible("k", "gpt-6-luna", "https://api.openai.com/v1", token_param="max_completion_tokens")
        body = json.loads(b.request("system", "user", PHOTO)[1])
        part = body["messages"][1]["content"][1]
        self.assertTrue(part["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(part["image_url"]["detail"], "high")
        self.assertIn("max_completion_tokens", body)

    def test_cost_and_retries(self):
        calls = []

        def transport(url, headers, body, timeout):
            calls.append(1)
            return (529, b'{"error": {"type": "overloaded"}}') if len(calls) == 1 else (200, anthropic_reply("{}"))

        b = llm.AnthropicAPI("k", "claude-sonnet-5-5", transport=transport, sleep=lambda s: None, price_in=2.0,
                             price_out=10.0)
        text, meta = b("s", "u", PHOTO)
        self.assertEqual((len(calls), text, meta["cost_usd"]), (2, "{}", 0.009))

    def test_a_refused_key_stops_with_the_keychain_item_named(self):
        b = llm.AnthropicAPI("k", "m", transport=lambda *a: (401, b"{}"), keychain="field-inspector-anthropic")
        with self.assertRaisesRegex(RuntimeError, "field-inspector-anthropic"):
            b("s", "u")

    def test_backend_for_reads_the_config(self):
        cfg = json.loads(inputs.HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
        for entry in cfg["models"]:
            self.assertEqual(llm.backend_for(entry, lambda item: "k").described()["model"], entry["model"])


class FirstPhoto(unittest.TestCase):
    def test_a_model_that_reads_nothing_on_its_first_photo_stops_unsaved(self):
        from owner import record_ai_runs as rec
        SCRATCH.mkdir(parents=True, exist_ok=True)
        old = rec.RUNS
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            rec.RUNS = Path(tmp)
            try:
                blind = lambda system, user, image=None: (reply(), {"cost_usd": 0.01})  # noqa: E731
                with self.assertRaisesRegex(RuntimeError, "may not be reaching it"):
                    rec.run_one(blind, "Blind", "p30", "blind", FIELDS, [], (1568, 1176), first=True)
                self.assertEqual(list(Path(tmp).rglob("*.json")), [])
                done, cached = rec.run_one(blind, "Blind", "p30", "blind", FIELDS, [], (1568, 1176))
                self.assertFalse(cached)
            finally:
                rec.RUNS = old


def reply(**fields):
    out = {f["id"]: {"status": "absent", "value": None, "label": None, "box": None} for f in FIELDS}
    out.update(fields)
    return json.dumps({"fields": out})


class Check(unittest.TestCase):
    def test_a_good_reply_inside_a_code_fence(self):
        text = "Here it is.\n```json\n" + reply(model={"status": "read", "value": " HPX-36B2 ", "label": "MODEL NO.",
                                                     "box": [0.4, 0.1, 0.6, 0.15]}) + "\n```"
        reads, held, problems = validate.read(text, FIELDS)
        self.assertEqual((problems, held), ([], []))
        self.assertEqual(reads["model"], {"status": "read", "value": "HPX-36B2", "label": "MODEL NO.",
                                          "box": [0.4, 0.1, 0.6, 0.15]})

    def test_shape_problems_call_for_the_repair(self):
        self.assertTrue(validate.read("no json here", FIELDS)[2])
        data = json.loads(reply())
        del data["fields"]["mca"]
        data["fields"]["serial"] = {"status": "read", "value": "X"}
        data["fields"]["volts"] = {"status": "maybe"}
        problems = validate.read(json.dumps(data), FIELDS)[2]
        self.assertEqual(len(problems), 3)

    def test_a_value_that_isnt_its_kind_is_held_and_a_bad_box_dropped(self):
        reads, held, problems = validate.read(reply(volts={"status": "read", "value": "sixty", "box": [0.5, 0.5, 0.4, 0.6]},
                                                    model={"status": "read", "value": "A1", "box": [0, 0, 1, 1]}), FIELDS)
        self.assertEqual(problems, [])
        self.assertEqual(held, [{"field": "volts", "value": "sixty", "why": "doesn't read as a volts value"}])
        self.assertEqual((reads["volts"]["status"], reads["volts"]["box"]), ("unreadable", None))
        self.assertIsNone(reads["model"]["box"])


class StandIn(unittest.TestCase):
    def test_the_stand_in_answers_from_the_key_and_passes_the_check(self):
        key = {"photos": {"p01": {"fields": {"model": {"value": "HPX-36B2", "box": [0.1, 0.1, 0.2, 0.2]},
                                             "mca": None}}}}
        text, meta = stand_in.Backend(key, FIELDS)("s", inputs.user_text("p01", 1568, 1176), PHOTO)
        reads, held, problems = validate.read(text, FIELDS)
        self.assertEqual((problems, held, reads["model"]["value"], reads["mca"]["status"]), ([], [], "HPX-36B2", "absent"))
        self.assertEqual(meta["cost_usd"], 0.0)


class Hashes(unittest.TestCase):
    def test_the_prompt_carries_every_field_and_the_hashes_move(self):
        system = inputs.system_prompt()
        self.assertTrue(all(f"`{f['id']}`" in system for f in FIELDS))
        a = inputs.input_hash(b"photo", inputs.user_text("p01", 10, 10))
        self.assertNotEqual(a, inputs.input_hash(b"photo2", inputs.user_text("p01", 10, 10)))
        self.assertEqual(len(inputs.prompt_hash()), 16)


class Redact(unittest.TestCase):
    def test_a_makers_word_is_replaced_and_counted(self):
        text, n = privacy.redact('{"value": "Plughco XE50", "note": "plughco"}', ["Plughco"])
        self.assertEqual((n, "lughco" in text, "[maker] XE50" in text), (2, False, True))
        self.assertEqual(privacy.redact("x", []), ("x", 0))


if __name__ == "__main__":
    unittest.main()
