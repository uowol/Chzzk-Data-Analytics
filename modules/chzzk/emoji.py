"""치지직 이모티콘 로컬 캐싱 및 치환"""

import logging
import re
from pathlib import Path

import requests

from . import api

logger = logging.getLogger(__name__)

EMOJI_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "emojis"
EMOJI_PATTERN = re.compile(r"\{:([a-zA-Z0-9_]+):\}")


class EmojiManager:
    """이모지팩을 로컬에 다운로드하고 emoji_id → 로컬 경로 매핑을 관리한다."""

    def __init__(self, streamer_id: str, cookies: dict):
        self._map: dict[str, str] = {}
        self._load(streamer_id, cookies)

    def _load(self, streamer_id: str, cookies: dict):
        try:
            packs, sub_packs = api.fetch_channelEmojiPacks(streamer_id, cookies)
        except Exception as e:
            logger.warning(f"이모지팩 조회 실패: {e}")
            return

        all_emojis = []
        for pack in (packs or []):
            all_emojis.extend(pack.get("emojis", []))
        for pack in (sub_packs or []):
            all_emojis.extend(pack.get("emojis", []))

        if not all_emojis:
            return

        EMOJI_DIR.mkdir(parents=True, exist_ok=True)

        for emoji in all_emojis:
            emoji_id = emoji["emojiId"]
            image_url = emoji["imageUrl"]
            ext = image_url.rsplit(".", 1)[-1]
            local_path = EMOJI_DIR / f"{emoji_id}.{ext}"

            if not local_path.exists():
                try:
                    resp = requests.get(image_url, timeout=10)
                    resp.raise_for_status()
                    local_path.write_bytes(resp.content)
                except Exception as e:
                    logger.warning(f"이모지 다운로드 실패 [{emoji_id}]: {e}")
                    continue

            self._map[emoji_id] = f"{emoji_id}.{ext}"

        logger.info(f"이모지 {len(self._map)}개 로드 완료")

    def resolve(self, text: str) -> str:
        """메시지 내 {:emoji_id:} 패턴을 [emoji:id:filename] 형식으로 치환한다."""
        if not self._map:
            return text
        return EMOJI_PATTERN.sub(self._replace, text)

    def _replace(self, match: re.Match) -> str:
        emoji_id = match.group(1)
        filename = self._map.get(emoji_id)
        if filename:
            return f"[emoji:{emoji_id}:{filename}]"
        return match.group(0)

    def get_path(self, emoji_id: str) -> Path | None:
        filename = self._map.get(emoji_id)
        if filename:
            return EMOJI_DIR / filename
        return None

    def __len__(self):
        return len(self._map)
