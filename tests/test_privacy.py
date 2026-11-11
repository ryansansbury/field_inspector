"""The privacy scan on JPEGs and PNGs built byte by byte: metadata of every kind, data after the end, an image in the
wrong place, a word under a mask, and the private list of masked words."""
import hashlib
import json
import tempfile
import unittest
import zlib
from pathlib import Path

from engine import privacy

HERE = Path(__file__).resolve().parent.parent


def seg(marker, body):
    return b"\xff" + bytes([marker]) + (len(body) + 2).to_bytes(2, "big") + body


JFIF = seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
TABLES = seg(0xDB, b"\x00" + bytes(64)) + seg(0xC0, b"\x08\x00\x10\x00\x10\x01\x01\x11\x00") + seg(0xC4, bytes(17))
SCAN = seg(0xDA, b"\x01\x01\x00\x00\x3f\x00") + b"\x12\xff\x00\x34\xff\xd0\x56"


def jpeg(*extra, tail=b""):
    return b"\xff\xd8" + JFIF + b"".join(extra) + TABLES + SCAN + b"\xff\xd9" + tail


def chunk(kind, body):
    return len(body).to_bytes(4, "big") + kind + body + zlib.crc32(kind + body).to_bytes(4, "big")


def png(*extra, tail=b""):
    head = chunk(b"IHDR", (16).to_bytes(4, "big") * 2 + b"\x08\x02\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + head + b"".join(extra) + chunk(b"IDAT", zlib.compress(bytes(800))) + \
        chunk(b"IEND", b"") + tail


class Markers(unittest.TestCase):
    def test_a_clean_file(self):
        self.assertEqual(privacy.jpeg_problems(jpeg()), [])

    def test_every_kind_of_metadata_is_caught(self):
        self.assertEqual(privacy.jpeg_problems(jpeg(seg(0xE1, b"Exif\x00\x00rest"))), ["an APP1 block (Exif)"])
        self.assertTrue(privacy.jpeg_problems(jpeg(seg(0xE1, b"http://ns.adobe.com/xap/1.0/\x00x"))))
        self.assertTrue(privacy.jpeg_problems(jpeg(seg(0xE2, b"ICC_PROFILE\x00x"))))
        self.assertTrue(privacy.jpeg_problems(jpeg(seg(0xED, b"Photoshop 3.0\x00x"))))
        self.assertEqual(privacy.jpeg_problems(jpeg(seg(0xFE, b"a note"))), ["a comment block"])

    def test_a_jfif_thumbnail_is_caught(self):
        thumb = seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x01\x01" + bytes(3))
        data = b"\xff\xd8" + thumb + TABLES + SCAN + b"\xff\xd9"
        self.assertEqual(privacy.jpeg_problems(data), ["an APP0 block that isn't a plain JFIF header"])

    def test_data_after_the_end_is_caught(self):
        self.assertEqual(privacy.jpeg_problems(jpeg(tail=b"\xff\xd8 a second picture")),
                         ["19 bytes after the end of the image"])

    def test_a_progressive_file_with_two_scans(self):
        data = b"\xff\xd8" + JFIF + TABLES + SCAN + seg(0xC4, bytes(17)) + SCAN + b"\xff\xd9"
        self.assertEqual(privacy.jpeg_problems(data), [])

    def test_not_a_jpeg(self):
        self.assertEqual(privacy.jpeg_problems(b"\x89PNG"), ["not a JPEG"])


class Scan(unittest.TestCase):
    def setUp(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.tmp.name)
        self.root.joinpath("data", "photos").mkdir(parents=True)
        self.root.joinpath("data", "ocr").mkdir(parents=True)
        photo = self.root.joinpath("data", "photos", "p01.jpg")
        photo.write_bytes(jpeg())
        manifest = {"photos": [{"id": "p01", "sha256": hashlib.sha256(jpeg()).hexdigest(),
                                "masks": [[0.5, 0.5, 0.7, 0.6]]}]}
        self.root.joinpath("data", "photos", "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.write_ocr([[0.1, 0.1, 0.2, 0.12]])

    def tearDown(self):
        self.tmp.cleanup()

    def write_ocr(self, boxes):
        lines = [{"text": "W", "conf": 1, "box": b, "words": [{"text": "W", "box": b}]} for b in boxes]
        self.root.joinpath("data", "ocr", "p01.json").write_text(json.dumps({"lines": lines}), encoding="utf-8")

    def test_a_clean_folder(self):
        out = privacy.scan(self.root)
        self.assertEqual((out["photos"], out["problems"]), (1, []))

    def test_a_word_under_a_mask(self):
        self.write_ocr([[0.55, 0.52, 0.6, 0.55]])
        self.assertIn("under a mask", " ".join(privacy.scan(self.root)["problems"]))

    def test_a_tilted_mask_covers_only_its_own_corners(self):
        """A mask on an angled shot is four corners, and a word inside the upright box around them but outside the
        corners themselves isn't under it."""
        entry = json.loads(self.root.joinpath("data", "photos", "manifest.json").read_text(encoding="utf-8"))
        entry["photos"][0]["masks"] = [{"quad": [[0.5, 0.5], [0.7, 0.4], [0.72, 0.46], [0.52, 0.56]]}]
        self.root.joinpath("data", "photos", "manifest.json").write_text(json.dumps(entry), encoding="utf-8")
        self.write_ocr([[0.5, 0.4, 0.56, 0.43]])
        self.assertEqual(privacy.scan(self.root)["problems"], [])
        self.write_ocr([[0.58, 0.46, 0.64, 0.49]])
        self.assertIn("under a mask", " ".join(privacy.scan(self.root)["problems"]))

    def test_an_unlogged_photo_and_a_stray_image(self):
        self.root.joinpath("data", "photos", "p02.jpg").write_bytes(jpeg(seg(0xFE, b"x")))
        self.root.joinpath("notes").mkdir()
        self.root.joinpath("notes", "IMG_0001.HEIC").write_bytes(b"x")
        problems = " ".join(privacy.scan(self.root)["problems"])
        self.assertIn("isn't in the masking log", problems)
        self.assertIn("a comment block", problems)
        self.assertIn("outside the published photo folders", problems)

    def test_the_readmes_screenshots_pass_only_with_nothing_but_pixels(self):
        gallery = self.root.joinpath("docs", "gallery")
        gallery.mkdir(parents=True)
        gallery.joinpath("job.png").write_bytes(png())
        self.assertEqual(privacy.scan(self.root)["problems"], [])
        gallery.joinpath("dryer.png").write_bytes(png(chunk(b"tEXt", b"Author\x00someone"), tail=b"more"))
        gallery.joinpath("how.jpg").write_bytes(jpeg())
        self.root.joinpath("docs", "phone.png").write_bytes(png())
        problems = privacy.scan(self.root)["problems"]
        self.assertEqual(problems[:2], ["docs/gallery/dryer.png: a tEXt block",
                                        "docs/gallery/dryer.png: 4 bytes after the end of the image"])
        self.assertEqual(len(problems), 4)
        self.assertEqual(sum("outside the published photo folders" in p for p in problems), 2)

    def test_the_private_list_is_counted_and_never_printed(self):
        self.root.joinpath("owner", "private").mkdir(parents=True)
        self.root.joinpath("owner", "private", "masked_words.json").write_text(json.dumps({"words": ["Plughco"]}),
                                                                               encoding="utf-8")
        self.root.joinpath("README.md").write_text("Made by plughco, and Plughco again.", encoding="utf-8")
        problems = privacy.scan(self.root)["problems"]
        self.assertEqual(problems, ["README.md holds 2 word(s) from the private list of masked words"])
        self.assertNotIn("lughco", " ".join(problems))


if __name__ == "__main__":
    unittest.main()
