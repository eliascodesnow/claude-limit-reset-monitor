import argparse
import hashlib
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import pytesseract
from PIL import Image, ImageFilter, ImageGrab, ImageOps

try:
    import pyttsx3
    _HAS_TTS = True
except ImportError:
    _HAS_TTS = False

try:
    import winsound
    _HAS_WINSOUND = True
except ImportError:
    _HAS_WINSOUND = False


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

SCAN_INTERVAL_SECONDS = 10
IDLE_SCAN_INTERVAL_SECONDS = 30  # used once a reset is already scheduled and the screen is unchanged

# None = entire primary screen. Otherwise (left, top, right, bottom).
OCR_REGION = None

REQUIRED_CONFIRMATIONS = 2
RESET_TIME_MATCH_TOLERANCE_SECONDS = 90
CONFLICT_TOLERANCE_SECONDS = 120
RESET_TRIGGER_TOLERANCE_SECONDS = 3
POST_ALERT_DELAY_SECONDS = 30

VOICE_ENABLED = True
BEEP_ENABLED = True

# Leave None if `tesseract --version` works in your shell.
TESSERACT_CMD = None

LOG_FILE = "claude_token_monitor.log"
STATE_FILE = "claude_token_monitor_state.json"


# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

logger = logging.getLogger("claude-token-monitor")
logger.setLevel(logging.INFO)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(_console_handler)

_file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(_file_handler)


# ------------------------------------------------------------
# Detection patterns
# ------------------------------------------------------------

TIME_PATTERN_12H = re.compile(
    r"\b(\d{1,2})\s*[:.]\s*(\d{2})\s*([AaPp])\s*[Mm]\b"
)

TIME_PATTERN_24H = re.compile(
    r"\b([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)\b"
)

RELATIVE_TIME_PATTERN = re.compile(
    r"\b(?:try\s+again|available|reset)\b.{0,80}?\bin\s+"
    r"(?:(\d{1,3})\s*(?:hours?|hrs?|h)\b\s*)?"
    r"(?:(\d{1,3})\s*(?:minutes?|mins?|m)\b\s*)?",
    re.IGNORECASE | re.DOTALL,
)

ANCHOR_PHRASES = ("try again at", "reset at", "available at")

LIMIT_PHRASES = (
    "try again at",
    "limit reached",
    "usage limit",
    "rate limit",
    "limit has been reached",
    "you've reached",
    "you have reached",
)


# ------------------------------------------------------------
# Data types
# ------------------------------------------------------------

@dataclass
class ResetDetection:
    reset_time: datetime
    source_text: str


class MonitorState:
    def __init__(self):
        self.scheduled_reset: Optional[datetime] = None
        self.last_alerted_reset: Optional[datetime] = None
        self.candidate_reset: Optional[datetime] = None
        self.candidate_confirmations = 0

    def register_detection(self, detected_time: datetime) -> bool:
        if self.candidate_reset is None:
            self.candidate_reset = detected_time
            self.candidate_confirmations = 1
            return False

        difference = abs((detected_time - self.candidate_reset).total_seconds())

        if difference <= RESET_TIME_MATCH_TOLERANCE_SECONDS:
            self.candidate_confirmations += 1
        else:
            self.candidate_reset = detected_time
            self.candidate_confirmations = 1

        if self.candidate_confirmations >= REQUIRED_CONFIRMATIONS:
            confirmed_time = self.candidate_reset
            self.candidate_reset = None
            self.candidate_confirmations = 0
            return self._accept_schedule(confirmed_time)

        return False

    def _accept_schedule(self, new_time: datetime) -> bool:
        if self.scheduled_reset is None:
            self.scheduled_reset = new_time
            return True

        existing_difference = abs((new_time - self.scheduled_reset).total_seconds())

        if existing_difference <= CONFLICT_TOLERANCE_SECONDS:
            return False

        logger.warning(
            "Ignoring conflicting reset time %s (existing schedule: %s).",
            format_datetime(new_time),
            format_datetime(self.scheduled_reset),
        )
        return False

    def should_alert(self, now: datetime) -> bool:
        if self.scheduled_reset is None:
            return False
        if self.last_alerted_reset == self.scheduled_reset:
            return False
        trigger_time = self.scheduled_reset - timedelta(seconds=RESET_TRIGGER_TOLERANCE_SECONDS)
        return now >= trigger_time

    def mark_alerted(self):
        if self.scheduled_reset is not None:
            self.last_alerted_reset = self.scheduled_reset
        self.scheduled_reset = None
        self.candidate_reset = None
        self.candidate_confirmations = 0

    def to_dict(self) -> dict:
        return {
            "scheduled_reset": self.scheduled_reset.isoformat() if self.scheduled_reset else None,
            "last_alerted_reset": self.last_alerted_reset.isoformat() if self.last_alerted_reset else None,
        }

    def load_dict(self, data: dict):
        if data.get("scheduled_reset"):
            self.scheduled_reset = datetime.fromisoformat(data["scheduled_reset"])
        if data.get("last_alerted_reset"):
            self.last_alerted_reset = datetime.fromisoformat(data["last_alerted_reset"])

    def save(self, path: Path):
        try:
            path.write_text(json.dumps(self.to_dict()), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save state: %s", exc)

    def load(self, path: Path):
        if not path.exists():
            return
        try:
            self.load_dict(json.loads(path.read_text(encoding="utf-8")))
            if self.scheduled_reset:
                logger.info("Restored scheduled reset from disk: %s", format_datetime(self.scheduled_reset))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Could not load saved state: %s", exc)


state = MonitorState()


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def format_datetime(value: Optional[datetime]) -> str:
    if value is None:
        return "None"
    return value.strftime("%Y-%m-%d %I:%M:%S %p")


def initialize_tesseract():
    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    try:
        version = pytesseract.get_tesseract_version()
        logger.info("Tesseract detected: %s", version)
    except Exception as exc:
        raise RuntimeError(
            "Tesseract OCR could not be initialized. Make sure Tesseract is installed and "
            "either `tesseract --version` works, or TESSERACT_CMD points to tesseract.exe."
        ) from exc


# ------------------------------------------------------------
# Screen capture / OCR
# ------------------------------------------------------------

def grab_screenshot() -> Image.Image:
    return ImageGrab.grab(bbox=OCR_REGION)


def preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    image = image.resize((image.width * 2, image.height * 2), Image.LANCZOS)
    image = image.filter(ImageFilter.SHARPEN)
    return image


def compute_screen_hash(image: Image.Image) -> str:
    thumb = image.convert("L").resize((160, 90))
    return hashlib.md5(thumb.tobytes()).hexdigest()


def ocr_image(image: Image.Image) -> str:
    processed = preprocess_image(image)
    return pytesseract.image_to_string(processed, config="--psm 6")


def normalize_ocr_text(text: str) -> str:
    text = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\b(\d{1,2})\s*[:.]\s*(\d{2})\s*([AaPp])\s*[Mm]\b", r"\1:\2 \3M", text)
    return text.strip()


# ------------------------------------------------------------
# Reset time parsing
# ------------------------------------------------------------

def _closest_match(matches, anchor_positions):
    if not anchor_positions:
        return matches[0]
    return min(
        matches,
        key=lambda match: min(abs(match.start() - anchor) for anchor in anchor_positions),
    )


def parse_absolute_time(text: str) -> Optional[datetime]:
    now = datetime.now()
    lower_text = text.lower()
    anchor_positions = [lower_text.find(p) for p in ANCHOR_PHRASES if p in lower_text]

    matches_12h = list(TIME_PATTERN_12H.finditer(text))
    if matches_12h:
        match = _closest_match(matches_12h, anchor_positions)
        hour, minute, meridiem = int(match.group(1)), int(match.group(2)), match.group(3).upper()
        if 1 <= hour <= 12 and 0 <= minute <= 59:
            try:
                target = datetime.strptime(f"{hour}:{minute:02d} {meridiem}", "%I:%M %p").replace(
                    year=now.year, month=now.month, day=now.day
                )
                if target < now - timedelta(minutes=1):
                    target += timedelta(days=1)
                return target
            except ValueError:
                pass

    # 24-hour fallback, only trusted near an anchor phrase to avoid false positives
    if anchor_positions:
        matches_24h = list(TIME_PATTERN_24H.finditer(text))
        if matches_24h:
            match = _closest_match(matches_24h, anchor_positions)
            hour, minute = int(match.group(1)), int(match.group(2))
            try:
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target < now - timedelta(minutes=1):
                    target += timedelta(days=1)
                return target
            except ValueError:
                pass

    return None


def parse_relative_time(text: str) -> Optional[datetime]:
    for match in RELATIVE_TIME_PATTERN.finditer(text):
        hours, minutes = match.group(1), match.group(2)
        if not hours and not minutes:
            continue
        delta = timedelta(hours=int(hours or 0), minutes=int(minutes or 0))
        if delta.total_seconds() <= 0:
            continue
        return datetime.now() + delta
    return None


def detect_reset_time(text: str) -> Optional[ResetDetection]:
    normalized = normalize_ocr_text(text)
    lower_text = normalized.lower()

    if not any(phrase in lower_text for phrase in LIMIT_PHRASES):
        return None

    absolute_time = parse_absolute_time(normalized)
    if absolute_time:
        return ResetDetection(reset_time=absolute_time, source_text=normalized)

    relative_time = parse_relative_time(normalized)
    if relative_time:
        return ResetDetection(reset_time=relative_time, source_text=normalized)

    return None


# ------------------------------------------------------------
# Notifications
# ------------------------------------------------------------

def voice_alert():
    if not _HAS_TTS:
        return
    try:
        engine = pyttsx3.init()
        engine.say("Your Claude tokens have been reset. You can continue chatting.")
        engine.runAndWait()
        engine.stop()
    except Exception as exc:
        logger.error("Voice notification failed: %s", exc)


def beep_alert():
    try:
        if _HAS_WINSOUND:
            for _ in range(3):
                winsound.Beep(1000, 200)
                winsound.Beep(1500, 300)
        else:
            for _ in range(3):
                sys.stdout.write("\a")
                sys.stdout.flush()
                time.sleep(0.3)
    except Exception as exc:
        logger.error("Beep notification failed: %s", exc)


def play_alert():
    print("\n" + "=" * 60)
    print("  CLAUDE TOKEN RESET DETECTED")
    print("  You can continue chatting.")
    print("=" * 60 + "\n")

    logger.info("Claude reset time reached. Triggering alert.")

    if VOICE_ENABLED:
        voice_alert()
    if BEEP_ENABLED:
        beep_alert()


# ------------------------------------------------------------
# Status display
# ------------------------------------------------------------

def print_status():
    now = datetime.now()
    scheduled = state.scheduled_reset

    if scheduled is None:
        message = f"Monitoring | No reset scheduled | Last scan: {now:%H:%M:%S}"
    else:
        remaining_seconds = int((scheduled - now).total_seconds())
        if remaining_seconds > 0:
            hours, remainder = divmod(remaining_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            message = f"Monitoring | Reset: {scheduled:%I:%M %p} | Remaining: {hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            message = f"Monitoring | Reset: {scheduled:%I:%M %p} | Alerting..."

    print("\r" + message + " " * 10, end="", flush=True)


# ------------------------------------------------------------
# Main loop
# ------------------------------------------------------------

def scan_screen_loop():
    logger.info("Monitoring screen for Claude usage limits. Press Ctrl+C to stop.")
    state_path = Path(STATE_FILE)
    last_hash = None

    while True:
        try:
            now = datetime.now()

            if state.should_alert(now):
                play_alert()
                state.mark_alerted()
                state.save(state_path)
                time.sleep(POST_ALERT_DELAY_SECONDS)
                last_hash = None
                continue

            screenshot = grab_screenshot()
            current_hash = compute_screen_hash(screenshot)

            skip_ocr = (
                state.scheduled_reset is not None
                and state.candidate_reset is None
                and current_hash == last_hash
            )

            if not skip_ocr:
                extracted_text = ocr_image(screenshot)
                detection = detect_reset_time(extracted_text)

                if detection:
                    logger.debug("Potential reset detected: %s", format_datetime(detection.reset_time))
                    confirmed = state.register_detection(detection.reset_time)
                    if confirmed:
                        logger.info("Reset confirmed: %s", format_datetime(state.scheduled_reset))
                        state.save(state_path)

            last_hash = current_hash
            print_status()

        except KeyboardInterrupt:
            print()
            logger.info("Monitor stopped by user.")
            break

        except Exception as exc:
            logger.exception("Scanning error: %s", exc)
            time.sleep(2)

        interval = (
            IDLE_SCAN_INTERVAL_SECONDS
            if state.scheduled_reset is not None and state.candidate_reset is None
            else SCAN_INTERVAL_SECONDS
        )
        time.sleep(interval)


# ------------------------------------------------------------
# CLI utilities
# ------------------------------------------------------------

def run_calibrate():
    initialize_tesseract()
    screenshot = grab_screenshot()
    screenshot.save("calibration_screenshot.png")
    text = ocr_image(screenshot)
    normalized = normalize_ocr_text(text)

    print("Saved raw screenshot to calibration_screenshot.png")
    print("-" * 60)
    print("OCR OUTPUT:")
    print(normalized)
    print("-" * 60)

    if any(p in normalized.lower() for p in LIMIT_PHRASES):
        print("A limit phrase was found in this text.")
        detection = detect_reset_time(text)
        if detection:
            print(f"Detected reset time: {format_datetime(detection.reset_time)}")
        else:
            print("No reset time could be parsed from this text.")
    else:
        print("No limit phrase currently visible on screen. This is normal if you haven't hit a limit.")


def run_test_alert():
    play_alert()


def main():
    parser = argparse.ArgumentParser(description="Claude Token Reset Monitor")
    parser.add_argument("--calibrate", action="store_true", help="Take one screenshot, run OCR, print the result, and exit.")
    parser.add_argument("--test-alert", action="store_true", help="Trigger the beep/voice alert immediately and exit.")
    args = parser.parse_args()

    try:
        if args.calibrate:
            run_calibrate()
            return
        if args.test_alert:
            run_test_alert()
            return

        initialize_tesseract()
        state.load(Path(STATE_FILE))
        logger.info("Scan interval: %ss (idle: %ss)", SCAN_INTERVAL_SECONDS, IDLE_SCAN_INTERVAL_SECONDS)
        logger.info("OCR region: %s", "entire primary screen" if OCR_REGION is None else OCR_REGION)
        logger.info("Voice: %s | Beep: %s", VOICE_ENABLED, BEEP_ENABLED)
        scan_screen_loop()

    except KeyboardInterrupt:
        logger.info("Monitor stopped.")
    except Exception as exc:
        logger.exception("Fatal startup error: %s", exc)
        print(f"\n[FATAL] {exc}")


if __name__ == "__main__":
    main()
