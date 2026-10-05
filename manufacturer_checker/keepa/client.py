"""メーカーに依存しないKeepa通信・トークン待機。単一スレッドで利用。"""
import math
import requests
import time
class KeepaTokenShortage(RuntimeError):
    """Keepaのトークン補充を待てば再実行できるエラー。"""

def is_token_shortage_error(error):
    message = str(error).lower()
    markers = (
        "not enough token",
        "insufficient token",
        "token limit",
        "tokens left",
        "refill",
        "too many requests",
        "rate limit",
        "status code: 429",
        "429 client error",
        "トークン不足",
    )
    return any(marker in message for marker in markers)

class KeepaClient:
    def __init__(self, api_key, *, session=None, sleep=time.sleep, logger=print,
                 token_wait_buffer=5, default_refill_rate=20):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Keepa APIキーが空です")
        if default_refill_rate <= 0 or token_wait_buffer < 0:
            raise ValueError("補充速度は正数、待機バッファは非負数が必要です")
        self._api_key = api_key.strip()
        self.session = session if session is not None else requests.Session()
        self.session.headers.update({"Accept-Encoding": "gzip", "User-Agent": "ManufacturerAmazonChecker/1.0"})
        self.base_url = "https://api.keepa.com"
        self.last_tokens_left = None
        self.refill_rate = None
        self.total_tokens_consumed = 0
        self.token_wait_buffer = token_wait_buffer
        self.default_refill_rate = default_refill_rate
        self._sleep = sleep
        self._logger = logger

    def _log(self, message):
        # requests例外にはkey付きURLが含まれるためログ・例外を伏せる。
        from urllib.parse import quote, quote_plus
        message = str(message)
        for value in (self._api_key, quote(self._api_key, safe=""), quote_plus(self._api_key)):
            message = message.replace(value, "[REDACTED]")
        self._logger(message)

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def wait_with_progress(self, wait_sec, reason):
        """長い待機中も1分ごとに残り時間を表示する。"""
        remaining = max(1, int(math.ceil(wait_sec)))
        self._log(f'\n{reason}')
        self._log(f'待機予定：約{math.ceil(remaining / 60)}分（{remaining}秒）')
        while remaining > 0:
            step = min(60, remaining)
            self._sleep(step)
            remaining -= step
            if remaining > 0:
                self._log(f'  トークン補充待ち：残り約{math.ceil(remaining / 60)}分')
        self._log('トークン待機が完了しました。処理を再開します。')

    def ensure_estimated_tokens(self, required_tokens, process_name):
        """直前レスポンスの残量と補充速度から、次の処理に必要な分を待つ。"""
        if self.last_tokens_left is None:
            return
        target = max(1, int(required_tokens)) + self.token_wait_buffer
        if self.last_tokens_left >= target:
            return
        rate = self.refill_rate if self.refill_rate and self.refill_rate > 0 else self.default_refill_rate
        shortage = target - self.last_tokens_left
        wait_sec = math.ceil(shortage / rate * 60) + 5
        self.wait_with_progress(wait_sec, f'{process_name}に必要なトークンが不足しています。現在 {self.last_tokens_left} / 目安 {target} / 補充速度 {rate}トークン/分')
        self.last_tokens_left = target

    def keepa_get(self, endpoint, params, retry=5):
        p = params.copy()
        p['key'] = self._api_key
        error_attempts = 0
        while True:
            try:
                response = self.session.get(self.base_url + endpoint, params=p, timeout=150)
                if response.status_code == 429:
                    try:
                        error_data = response.json()
                    except Exception:
                        error_data = {}
                    self.last_tokens_left = error_data.get('tokensLeft', self.last_tokens_left)
                    self.refill_rate = error_data.get('refillRate', self.refill_rate)
                    raise KeepaTokenShortage(f"HTTP 429: {error_data.get('error') or 'Keepa API token shortage'}")
                response.raise_for_status()
                data = response.json()
                if data.get('error'):
                    message = str(data['error'])
                    if is_token_shortage_error(message):
                        raise KeepaTokenShortage(message)
                    raise RuntimeError(message)
                self.last_tokens_left = data.get('tokensLeft', self.last_tokens_left)
                self.refill_rate = data.get('refillRate', self.refill_rate)
                consumed = data.get('tokensConsumed', 0) or 0
                self.total_tokens_consumed += consumed
                self._log(f'残りトークン：{self.last_tokens_left} / 今回消費：{consumed}' + (f' / 補充速度：{self.refill_rate}/分' if self.refill_rate is not None else ''))
                return data
            except KeepaTokenShortage:
                raise
            except Exception as e:
                error_attempts += 1
                if error_attempts >= retry:
                    raise RuntimeError("Keepa通信に失敗しました（APIキーを保護するため詳細URLは非表示）") from None
                wait_sec = 8 * error_attempts
                self._log(f'Keepa通信エラー：{e} / {wait_sec}秒後に再試行します。')
                self._sleep(wait_sec)

    def keepa_get_with_wait(self, endpoint, params, estimated_tokens, process_name):
        """トークン不足なら補充まで待機し、同じリクエストを必ず再開する。"""
        target = max(1, int(estimated_tokens)) + self.token_wait_buffer
        while True:
            self.ensure_estimated_tokens(estimated_tokens, process_name)
            try:
                return self.keepa_get(endpoint, params)
            except Exception as e:
                if not isinstance(e, KeepaTokenShortage) and (not is_token_shortage_error(e)):
                    raise
                rate = self.refill_rate if self.refill_rate and self.refill_rate > 0 else self.default_refill_rate
                current = self.last_tokens_left if self.last_tokens_left is not None else 0
                shortage = max(1, target - current)
                wait_sec = max(60, math.ceil(shortage / rate * 60) + 5)
                self.wait_with_progress(wait_sec, f'{process_name}中にKeepaのトークンが不足しました。現在 {current} / 目安 {target} / 補充速度 {rate}トークン/分。補充後、同じ位置から自動再開します。')
                self.last_tokens_left = target
