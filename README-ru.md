# ZeroNet [![tests](https://github.com/ZeroNetX/ZeroNet/actions/workflows/tests.yml/badge.svg)](https://github.com/ZeroNetX/ZeroNet/actions/workflows/tests.yml) [![Documentation](https://img.shields.io/badge/docs-faq-brightgreen.svg)](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/faq/) [![Help](https://img.shields.io/badge/keep_this_project_alive-donate-yellow.svg)](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/help_zeronet/donate/) [![Docker Pulls](https://img.shields.io/docker/pulls/canewsin/zeronet)](https://hub.docker.com/r/canewsin/zeronet)

[简体中文](./README-zh-cn.md)
[English](./README.md)

Децентрализованные вебсайты, использующие криптографию Bitcoin и протокол BitTorrent — https://zeronet.dev ([Зеркало в ZeroNet](http://127.0.0.1:43110/1ZeroNetyV5mKY9JF1gsm82TuBXHpfdLX/)). В отличии от Bitcoin, ZeroNet'у не требуется блокчейн для работы, однако он использует ту же криптографию, чтобы обеспечить сохранность и проверку данных.

## Зачем?

- Мы верим в открытую, свободную, и неподдающуюся цензуре сеть и связь.
- Нет единой точки отказа: Сайт остаётся онлайн, пока его обслуживает хотя бы 1 пир.
- Нет затрат на хостинг: Сайты обслуживаются посетителями.
- Невозможно отключить: Он нигде, потому что он везде.
- Скорость и возможность работать без Интернета: Вы сможете получить доступ к сайту, потому что его копия хранится на вашем компьютере и у ваших пиров.

## Особенности

- Обновление сайтов в реальном времени
- Поддержка доменов `.bit` ([Namecoin](https://www.namecoin.org))
- Легкая установка: просто распакуйте и запустите
- Клонирование сайтов "в один клик"
- Беспарольная [BIP32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki)
  авторизация: Ваша учетная запись защищена той же криптографией, что и ваш Bitcoin-кошелек
- Встроенный SQL-сервер с синхронизацией данных P2P: Позволяет упростить разработку сайта и ускорить загрузку страницы
- Анонимность: Полная поддержка сети Tor, используя скрытые службы `.onion` вместо адресов IPv4
- Зашифрованное TLS подключение
- Автоматическое открытие UPnP–порта
- Плагин для поддержки нескольких пользователей (openproxy)
- Работа с любыми браузерами и операционными системами

## Текущие ограничения

- Файловые транзакции не сжаты
- Нет приватных сайтов

## Как это работает?

- После запуска `zeronet.py` вы сможете посещать сайты в ZeroNet, используя адрес
  `http://127.0.0.1:43110/{zeronet_адрес}`
  (Например: `http://127.0.0.1:43110/1HELLoE3sFD9569CLCbHEAVqvqV7U2Ri9d`).
- Когда вы посещаете новый сайт в ZeroNet, он пытается найти пиров с помощью протокола BitTorrent,
  чтобы скачать у них файлы сайта (HTML, CSS, JS и т.д.).
- После посещения сайта вы тоже становитесь его пиром.
- Каждый сайт содержит файл `content.json`, который содержит SHA512 хеши всех остальные файлы
  и подпись, созданную с помощью закрытого ключа сайта.
- Если владелец сайта (тот, кто владеет закрытым ключом для адреса сайта) изменяет сайт, он
  подписывает новый `content.json` и публикует его для пиров. После этого пиры проверяют целостность `content.json`
  (используя подпись), скачвают изменённые файлы и распространяют новый контент для других пиров.

[Презентация о криптографии ZeroNet, обновлениях сайтов, многопользовательских сайтах »](https://docs.google.com/presentation/d/1_2qK1IuOKJ51pgBvllZ9Yu7Au2l551t3XBgyTSvilew/pub?start=false&loop=false&delayms=3000)
[Часто задаваемые вопросы »](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/faq/)
[Документация разработчика ZeroNet »](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/site_development/getting_started/)

## Скриншоты

![Screenshot](https://i.imgur.com/H60OAHY.png)
![ZeroTalk](https://zeronet.io/docs/img/zerotalk.png)
[Больше скриншотов в документации ZeroNet »](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/using_zeronet/sample_sites/)

## Как присоединиться?

### Windows

- Скачайте и распакуйте архив [ZeroNet-win.zip](https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-win.zip) (26МБ)
- Запустите `ZeroNet.exe`

### macOS

- Скачайте и распакуйте архив [ZeroNet-mac.zip](https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-mac.zip) (14МБ)
- Запустите `ZeroNet.app`

### Linux (64 бит)

- Скачайте и распакуйте архив [ZeroNet-linux.zip](https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-linux.zip) (14МБ)
- Запустите `./ZeroNet.sh`

> **Note**
> Запустите таким образом: `./ZeroNet.sh --ui_ip '*' --ui_restrict ваш_ip_адрес`, чтобы разрешить удалённое подключение к веб–интерфейсу.

### Docker

Официальный образ находится здесь: https://hub.docker.com/r/canewsin/zeronet/

### Android (arm, arm64, x86)

- Для работы требуется Android как минимум версии 5.0 Lollipop
- [<img src="https://play.google.com/intl/en_us/badges/images/generic/en_badge_web_generic.png" 
     alt="Download from Google Play" 
     height="80">](https://play.google.com/store/apps/details?id=in.canews.zeronetmobile)
- Скачать APK: https://github.com/canewsin/zeronet_mobile/releases

### Android (arm, arm64, x86) Облегчённый клиент только для просмотра (1МБ)

- Для работы требуется Android как минимум версии 4.1 Jelly Bean
- [<img src="https://play.google.com/intl/en_us/badges/images/generic/en_badge_web_generic.png" 
     alt="Download from Google Play" 
     height="80">](https://play.google.com/store/apps/details?id=dev.zeronetx.app.lite)

### Установка из исходного кода

```sh
wget https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-src.zip
unzip ZeroNet-src.zip
cd ZeroNet
sudo apt-get update
sudo apt-get install python3-pip
sudo python3 -m pip install -r requirements.txt
```
- Запустите `python3 zeronet.py`

Откройте приветственную страницу ZeroHello в вашем браузере по ссылке http://127.0.0.1:43110/

## Как мне создать сайт в ZeroNet?

- Кликните на **⋮** > **"Create new, empty site"** в меню на сайте [ZeroHello](http://127.0.0.1:43110/1HELLoE3sFD9569CLCbHEAVqvqV7U2Ri9d).
- Вы будете **перенаправлены** на совершенно новый сайт, который может быть изменён только вами!
- Вы можете найти и изменить контент вашего сайта в каталоге **data/[адрес_вашего_сайта]**
- После изменений откройте ваш сайт, переключите влево кнопку "0" в правом верхнем углу, затем нажмите кнопки **sign** и **publish** внизу

Следующие шаги: [Документация разработчика ZeroNet](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/site_development/getting_started/)

## Поддержите проект

- Bitcoin: 1ZeroNetyV5mKY9JF1gsm82TuBXHpfdLX (Рекомендуем)
- LiberaPay: https://liberapay.com/PramUkesh
- Paypal: https://paypal.me/PramUkesh
- Другие способы: [Donate](!https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/help_zeronet/donate/#help-to-keep-zeronet-development-alive)

#### Спасибо!

- Здесь вы можете получить больше информации, помощь, прочитать список изменений и исследовать ZeroNet сайты: https://www.reddit.com/r/zeronetx/
- Общение происходит на канале [#zeronet @ FreeNode](https://kiwiirc.com/client/irc.freenode.net/zeronet) или в [Gitter](https://gitter.im/canewsin/ZeroNet)
- Электронная почта: canews.in@gmail.com
