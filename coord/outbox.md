# Ответы сессии на Mac mini

## №1 — замер Chatterbox — ГОТОВО (коммит 80f85b8)
Apple M4 Pro, RAM 24 ГБ, macOS 26.6.2, torch 2.14.0 (MPS доступен).

| устройство | загрузка, с | RTF (без первой фразы) | пик RAM процесса, ГБ | память MPS, ГБ |
|---|---|---|---|---|
| cpu | 7.2 | 2.34 | 6.5 | — |
| mps | 8.5 | 1.04 | 4.9 | 3.6 |

MPS не падал. Первая фраза (прогрев): CPU 3.95, MPS 3.7. На MPS фразы 2–5: 1.24 / 0.96 / 0.93 / 1.02.
Инструкции в шапке скрипта не хватает двух пакетов — доставил:
- `transformers==5.2.0` (иначе `ModuleNotFoundError: No module named 'transformers'`);
- `setuptools<81` (perth делает `from pkg_resources import ...`; без него `PerthImplicitWatermarker` = None →
  `TypeError: 'NoneType' object is not callable`).
Стоит дописать их в шапку `tools/mac_bench.py`.

## №2 — сборка italo-tutor — ГОТОВО (ветка claude/funny-thompson-nhd4kq, 123ba0f)
Xcode 27.0 (27A266a), Flutter 3.35.5 (поставлен отдельно в ~/flutter-3.35.5; системный — 3.47.2).
- `flutter pub get` — OK.
- `flutter analyze` — No issues found.
- `flutter test` — All tests passed (18).
- `flutter build macos` — OK после двух локальных правок (в italo-tutor НЕ закоммичены):
  1. Xcode 27 не принимает deployment target ниже 12.0: `MACOSX_DEPLOYMENT_TARGET is set to 10.15, but the range
     of supported deployment target versions is 12.0 to 27.0.x`. Поднял до 12.0 в `macos/Podfile` (platform +
     post_install для всех подов) и `macos/Runner.xcodeproj/project.pbxproj`. Для CI на свежем Xcode это тоже понадобится.
  2. Flutter 3.35.5 + Xcode 27: `lipo -verify_arch arm64 x86_64` → `-verify_arch requires exactly one input file`,
     сборка падала на `release_unpack_macos` («does not contain architectures»). Пропатчил
     `packages/flutter_tools/lib/src/build_system/targets/darwin.dart` в локальном SDK (проверка по одной архитектуре).
     Это баг Flutter SDK, не проекта.
- Собранное: `~/italo/italo-tutor/build/macos/Build/Products/Release/italo_tutor.app` (52.2 МБ).
- `flutter run -d macos` — приложение открылось (Debug), ждёт ручной проверки владельца.

## №3 — запасная модель Паоло — ЖДЁТ
Ключи Gemini приложение берёт из своего хранилища (вводятся в приложении); на Mac их нет, вводить ключи сам я не могу.
Нужно: владельцу ввести ключ Gemini в запущенном приложении. После этого перезапущу с
`liveModel = 'gemini-0.0-none'`, пройду стартовую проверку/урок и верну `liveModel`.

### №3 — обновление: блокировка по VPN
Стартовая проверка: «нет VPN / нет связи». Приложение требует встроенный Xray-туннель: `vpn/xray` рядом с .app
и `italo_vpn.json` (в `vpn/` или `~/key/`) — на Mac их нет. Сам Mac до Gemini достаёт напрямую (выход DE,
generativelanguage.googleapis.com отвечает 403 «нужен ключ»). Спросил владельца: положить конфиг туннеля
(xray поставлю из Homebrew) или временно пропускать туннель при не-RU выходе (локально, без коммита). Жду.
