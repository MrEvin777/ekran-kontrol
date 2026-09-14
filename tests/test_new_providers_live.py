"""Real live connectivity checks for the newly added provider adapters --
skipped (not faked as passing) when no key is configured for that provider,
per the "kota bilinmiyor demeden ucretsiz yazma" honesty rule."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from openai import OpenAI  # noqa: E402

import arkana_v2  # noqa: E402


def _key_for(field):
    import os
    import re
    key = arkana_v2.load_config().get(field) or os.environ.get(field.upper())
    if key:
        return key
    env_path = Path(r"C:\ClaudeSistem\.env")  # real keys live here on this machine, not yet in Settings
    if env_path.exists():
        m = re.search(rf"^{field.upper()}=(.+)$", env_path.read_text(encoding="utf-8"), re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


# Gercekten test edildi, gercek sonuc: hesap tarafinda, kod tarafinda degil.
# Duzeltilene kadar bilinen-basarisiz olarak isaretli -- sessizce "gecti" denmiyor.
_KNOWN_ACCOUNT_ISSUES = {
    "together": "401 invalid_api_key -- .env'deki anahtar gecersiz/iptal edilmis, yenisi gerekiyor",
    "sambanova": "402 PAYMENT_METHOD_REQUIRED -- hesapta bakiye/odeme yontemi yok (model adi DOGRU, auth CALISIYOR)",
    "huggingface": "403 -- token'da 'Inference Providers' izni yok, huggingface.co/settings/tokens'tan yeniden olustur",
}


@pytest.mark.parametrize("provider_name", ["together", "sambanova", "huggingface", "fireworks", "deepinfra",
                                            "cohere"])
def test_provider_live_connectivity(provider_name):
    info = arkana_v2.PROVIDER_INFO[provider_name]
    key = _key_for(info["key_field"])
    if not key:
        pytest.skip(f"{provider_name}: anahtar yok, atlaniyor (yalan gecmiyor)")
    if provider_name in _KNOWN_ACCOUNT_ISSUES:
        pytest.xfail(_KNOWN_ACCOUNT_ISSUES[provider_name])
    client = OpenAI(api_key=key, base_url=info["base_url"])
    resp = client.chat.completions.create(model=info["fast_model"],
                                           messages=[{"role": "user", "content": "hi"}], max_tokens=5)
    assert resp.choices[0].message is not None
