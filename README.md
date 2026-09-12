# Ekran Kontrol (Arkana Yaslan)

Kisisel AI bilgisayar asistani. Ekrani gorur, sesli/yazili konusur, dosya/komut
islemleri yapar, birden fazla AI saglayicisi arasinda otomatik gecis yapar.

## Ozellikler
- Ekran gorme (canli izleme) + OCR
- Sesli komut (mikrofon) + sesli yanit
- Dosya okuma/yazma/silme (diff gosterimi + geri alma)
- Komut/kod calistirma (onayli)
- Kalici hafiza (Qdrant, yerel)
- Coklu AI saglayici: OpenAI, Anthropic, Gemini, Groq, Cerebras, Mistral,
  NVIDIA NIM, OpenRouter, GitHub Models, Ollama (yerel/ucretsiz yedek)
- Model router: basit sorularda hizli, kodlamada guclu model
- Alt-ajanlara gorev devretme (arastirmaci/kodlayici/test uzmani)
- MCP client (dis MCP sunuculara baglanma)
- n8n entegrasyonu (ekran yakalama endpoint'i)

## Kurulum
```bash
pip install -r requirements.txt
```
Gerekli: Python 3.10+, Node.js (hyper-router icin), Ollama (opsiyonel, yerel yedek).

## Calistirma
```bash
python arkana_v2.py
```
Veya `OmniAI_Ekran_Kontrol_Baslat.vbs` dosyasina cift tiklayin (konsol penceresi acmadan calisir).

## Ayarlar
Uygulama icindeki "Ayarlar" penceresinden kendi API anahtarlarinizi girin
(OpenAI, Anthropic, Gemini, Groq, Cerebras, Mistral, NVIDIA NIM, OpenRouter,
GitHub Models). Hicbir anahtar girmezseniz sistem yerel Ollama ile calisir
(ekran gormek icin gorsel destekli bir Ollama modeli gerekir).

## Guvenlik
- Tum guclu islemler (tiklama/yazma disinda) sadece bu uygulama icinde calisir,
  disaridan (ag) tetiklenemez.
- Kritik islemler (dosya silme/ustune yazma, komut calistirma, git push,
  e-posta gonderme) her zaman kullanici onayi ister.
- API anahtarlari sadece yerel `~/.omniai/config.json` dosyasinda saklanir,
  bu repoya dahil edilmez (.gitignore).

## Not
`n8n/` ve `security/` klasorleri (yerel veri/bagimliliklar icerdikleri icin)
bu repoya dahil edilmemistir.
