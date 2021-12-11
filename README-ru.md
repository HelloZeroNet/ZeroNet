# ZeroNet [![tests](https://github.com/ZeroNetX/ZeroNet/actions/workflows/tests.yml/badge.svg)](https://github.com/ZeroNetX/ZeroNet/actions/workflows/tests.yml) [![Documentation](https://img.shields.io/badge/docs-faq-brightgreen.svg)](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/faq/) [![Help](https://img.shields.io/badge/keep_this_project_alive-donate-yellow.svg)](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/help_zeronet/donate/) [![Docker Pulls](https://img.shields.io/docker/pulls/canewsin/zeronet)](https://hub.docker.com/r/canewsin/zeronet)

[简体中文](./README-zh-cn.md)
[English](./README.md)

Децентрализованные вебсайты использующие Bitcoin криптографию и BitTorrent сеть - https://zeronet.dev


## Зачем?

* Мы верим в открытую, свободную, и не отцензуренную сеть и коммуникацию.
* Нет единой точки отказа: Сайт онлайн пока по крайней мере 1 пир обслуживает его.
* Никаких затрат на хостинг: Сайты обслуживаются посетителями.
* Невозможно отключить: Он нигде, потому что он везде.
* Быстр и работает оффлайн: Вы можете получить доступ к сайту, даже если Интернет недоступен.


## Особенности
 * Обновляемые в реальном времени сайты
 * Поддержка Namecoin .bit доменов
 * Лёгок в установке: распаковал & запустил
 * Клонирование вебсайтов в один клик
 * Password-less [BIP32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki)
   based authorization: Ваша учетная запись защищена той же криптографией, что и ваш Bitcoin-кошелек
 * Встроенный SQL-сервер с синхронизацией данных P2P: Позволяет упростить разработку сайта и ускорить загрузку страницы
 * Анонимность: Полная поддержка сети Tor с помощью скрытых служб .onion вместо адресов IPv4
 * TLS зашифрованные связи
 * Автоматическое открытие uPnP порта
 * Плагин для поддержки многопользовательской (openproxy)
 * Работает с любыми браузерами и операционными системами


## Как это работает?

* После запуска `zeronet.py` вы сможете посетить зайты (zeronet сайты) используя адрес
  `http://127.0.0.1:43110/{zeronet_address}`
(например. `http://127.0.0.1:43110/1HELLoE3sFD9569CLCbHEAVqvqV7U2Ri9d`).
* Когда вы посещаете новый сайт zeronet, он пытается найти пиров с помощью BitTorrent
  чтобы загрузить файлы сайтов (html, css, js ...) из них.
* Каждый посещенный зайт также обслуживается вами. (Т.е хранится у вас на компьютере)
* Каждый сайт содержит файл `content.json`, который содержит все остальные файлы в хэше sha512
  и подпись, созданную с использованием частного ключа сайта.
* Если владелец сайта (у которого есть закрытый ключ для адреса сайта) изменяет сайт, то он/она
  подписывает новый `content.json` и публикует его для пиров. После этого пиры проверяют целостность `content.json`
  (используя подпись), они загружают измененные файлы и публикуют новый контент для других пиров.

####  [Слайд-шоу о криптографии ZeroNet, обновлениях сайтов, многопользовательских сайтах »](https://docs.google.com/presentation/d/1_2qK1IuOKJ51pgBvllZ9Yu7Au2l551t3XBgyTSvilew/pub?start=false&loop=false&delayms=3000)
####  [Часто задаваемые вопросы »](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/faq/)

####  [Документация разработчика ZeroNet »](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/site_development/getting_started/)


## Скриншоты

![Screenshot](https://i.imgur.com/H60OAHY.png)
![ZeroTalk](https://zeronet.io/docs/img/zerotalk.png)

#### [Больше скриншотов в ZeroNet документации »](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/using_zeronet/sample_sites/)


## Как вступить

* Скачайте ZeroBundle пакет:
  * [Microsoft Windows](https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-win.zip)
  * [Apple macOS](https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-mac.zip)
  * [Linux 64-bit](https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-linux.zip)
  * [Linux 32-bit](https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-linux.zip)
* Распакуйте где угодно
* Запустите `ZeroNet.exe` (win), `ZeroNet(.app)` (osx), `ZeroNet.sh` (linux)

### Linux терминал

* `wget https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-linux.zip`
* `unzip ZeroNet-linux.zip`
* `cd ZeroNet-linux`
* Запустите с помощью `./ZeroNet.sh`

Он загружает последнюю версию ZeroNet, затем запускает её автоматически.

#### Ручная установка для Debian Linux

* `wget https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-src.zip`
* `unzip ZeroNet-src.zip`
* `cd ZeroNet`
* `sudo apt-get update`
* `sudo apt-get install python3-pip`
* `sudo python3 -m pip install -r requirements.txt`
* Запустите с помощью `python3 zeronet.py`
* Откройте http://127.0.0.1:43110/ в вашем браузере.

### [Arch Linux](https://www.archlinux.org)

* `git clone https://aur.archlinux.org/zeronet.git`
* `cd zeronet`
* `makepkg -srci`
* `systemctl start zeronet`
* Откройте http://127.0.0.1:43110/ в вашем браузере.

Смотрите [ArchWiki](https://wiki.archlinux.org)'s [ZeroNet
article](https://wiki.archlinux.org/index.php/ZeroNet) для дальнейшей помощи.

### [Gentoo Linux](https://www.gentoo.org)

* [`layman -a raiagent`](https://github.com/leycec/raiagent)
* `echo '>=net-vpn/zeronet-0.5.4' >> /etc/portage/package.accept_keywords`
* *(Опционально)* Включить поддержку Tor: `echo 'net-vpn/zeronet tor' >>
  /etc/portage/package.use`
* `emerge zeronet`
* `rc-service zeronet start`
* Откройте http://127.0.0.1:43110/ в вашем браузере.

Смотрите `/usr/share/doc/zeronet-*/README.gentoo.bz2` для дальнейшей помощи.

### [FreeBSD](https://www.freebsd.org/)

* `pkg install zeronet` or `cd /usr/ports/security/zeronet/ && make install clean`
* `sysrc zeronet_enable="YES"`
* `service zeronet start`
* Откройте http://127.0.0.1:43110/ в вашем браузере.

### [Vagrant](https://www.vagrantup.com/)

* `vagrant up`
* Подключитесь к VM с помощью `vagrant ssh`
* `cd /vagrant`
* Запустите `python3 zeronet.py --ui_ip 0.0.0.0`
* Откройте http://127.0.0.1:43110/ в вашем браузере.

### [Docker](https://www.docker.com/)
* `docker run -d -v <local_data_folder>:/root/data -p 15441:15441 -p 127.0.0.1:43110:43110 canewsin/zeronet`
* Это изображение Docker включает в себя прокси-сервер Tor, который по умолчанию отключён.
  Остерегайтесь что некоторые хостинг-провайдеры могут не позволить вам запускать Tor на своих серверах.
  Если вы хотите включить его,установите переменную среды `ENABLE_TOR` в` true` (по умолчанию: `false`) Например:

 `docker run -d -e "ENABLE_TOR=true" -v <local_data_folder>:/root/data -p 15441:15441 -p 127.0.0.1:43110:43110 canewsin/zeronet`
* Откройте http://127.0.0.1:43110/ в вашем браузере.

### [Virtualenv](https://virtualenv.readthedocs.org/en/latest/)

* `virtualenv env`
* `source env/bin/activate`
* `pip install msgpack gevent`
* `python3 zeronet.py`
* Откройте http://127.0.0.1:43110/ в вашем браузере.

## Текущие ограничения

* Файловые транзакции не сжаты
* Нет приватных сайтов


## Как я могу создать сайт в Zeronet?

Завершите работу zeronet, если он запущен

```bash
$ zeronet.py siteCreate
...
- Site private key (Приватный ключ сайта): 23DKQpzxhbVBrAtvLEc2uvk7DZweh4qL3fn3jpM3LgHDczMK2TtYUq
- Site address (Адрес сайта): 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2
...
- Site created! (Сайт создан)
$ zeronet.py
...
```

Поздравляем, вы закончили! Теперь каждый может получить доступ к вашему зайту используя
`http://localhost:43110/13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2`

Следующие шаги: [ZeroNet Developer Documentation](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/site_development/getting_started/)


## Как я могу модифицировать Zeronet сайт?

* Измените файлы расположенные в data/13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2 директории.
  Когда закончите с изменением:

```bash
$ zeronet.py siteSign 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2
- Signing site (Подпись сайта): 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2...
Private key (Приватный ключ) (input hidden):
```

* Введите секретный ключ, который вы получили при создании сайта, потом:

```bash
$ zeronet.py sitePublish 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2
...
Site:13DNDk..bhC2 Publishing to 3/10 peers...
Site:13DNDk..bhC2 Successfuly published to 3 peers
- Serving files....
```

* Вот и всё! Вы успешно подписали и опубликовали свои изменения.


## Поддержите проект
- Bitcoin: 1ZeroNetyV5mKY9JF1gsm82TuBXHpfdLX (Preferred)
- LiberaPay: https://liberapay.com/PramUkesh
- Paypal: https://paypal.me/PramUkesh
- Others: [Donate](!https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/help_zeronet/donate/#help-to-keep-zeronet-development-alive)


#### Спасибо!

* Больше информации, помощь, журнал изменений, zeronet сайты: https://www.reddit.com/r/zeronetx/
* Приходите, пообщайтесь с нами: [#zeronet @ FreeNode](https://kiwiirc.com/client/irc.freenode.net/zeronet) или на [gitter](https://gitter.im/canewsin/ZeroNet)
* Email: canews.in@gmail.com
