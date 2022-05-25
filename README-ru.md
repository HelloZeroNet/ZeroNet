# zeronet-conservancy

Минималистичный форк [ZeroNet](https://github.com/HelloZeroNet/ZeroNet) с
поддержкой onion-v3 tor (и возможных других необходимых фиксов и закрытий
уязвимостей)

## Зачем форк?

Нам нужен форк работающий с onion-v3 и не зависящий от доверия к одному или двум
личностям. Этот форк нужен прямо сейчас. Данный форк представляет из себя
минимальный [сет изменений по сравнению с последним коммитом
ZeroNet/py3](https://github.com/HelloZeroNet/ZeroNet/compare/py3...zeronet-conservancy:master)
, их легко проверить самостоятельно.

Этот форк является временной мерой и может закончиться, если/когда автор сего
форка решит, что существует альтернативный, активный, заслуживающий доверия
форк.

## Зачем?

* Мы верим в открытую, свободную, и не поддающуюся цензуре сеть и коммуникацию.
* Нет единой точки отказа: Сайт онлайн пока по крайней мере 1 пир обслуживает его.
* Никаких затрат на хостинг: Сайты обслуживаются посетителями.
* Невозможно отключить: Он нигде, потому что он везде.
* Быстр и работает оффлайн: Вы можете получить доступ к сайту, даже если Интернет недоступен.

## Особенности
 * Обновляемые в реальном времени сайты
 * Клонирование вебсайтов в один клик
 * Авторизация без паролей, с использованием пары публичный/приватный ключ
 * Встроенный SQL-сервер с синхронизацией данных P2P: позволяет упростить разработку сайта
 * Анонимность: поддержка сети Tor с помощью скрытых служб .onion (включая onion-v3)
 * TLS зашифрованные связи (в клирнете)
 * Автоматическое открытие uPnP порта (опционально)
 * Плагин для поддержки многопользовательской (openproxy)
 * Работает с любыми браузерами и операционными системами


## Как это работает?

* После запуска `zeronet.py` вы сможете посетить зайты (zeronet сайты) используя адрес
  `http://127.0.0.1:43110/{zeronet_address}`
(например. `http://127.0.0.1:43110/1HeLLo4uzjaLetFx6NH3PMwFP3qbRbTf3D`).
* Когда вы посещаете новый сайт zeronet, он пытается найти пиров с помощью BitTorrent
  чтобы загрузить файлы сайтов (html, css, js ...) из них.
* Каждый посещенный зайт также обслуживается вами. (Т.е хранится у вас на компьютере)
* Каждый сайт содержит файл `content.json`, который содержит все остальные файлы в хэше sha512
  и подпись, созданную с использованием частного ключа сайта.
* Если владелец сайта (у которого есть закрытый ключ для адреса сайта) изменяет сайт, то он/она
  подписывает новый `content.json` и публикует его для пиров. После этого пиры проверяют целостность `content.json`
  (используя подпись), они загружают измененные файлы и публикуют новый контент для других пиров.

####  [Слайд-шоу о криптографии ZeroNet, обновлениях сайтов, многопользовательских сайтах »](https://docs.google.com/presentation/d/1_2qK1IuOKJ51pgBvllZ9Yu7Au2l551t3XBgyTSvilew/pub?start=false&loop=false&delayms=3000)
####  [Часто задаваемые вопросы »](https://zeronet.io/docs/faq/)

####  [Документация разработчика ZeroNet »](https://zeronet.io/docs/site_development/getting_started/)


#### [Скриншоты в ZeroNet документации »](https://zeronet.io/docs/using_zeronet/sample_sites/)

## Как вступить

### Install from source

 - clone this repo
 - install python3 and pip if needed (the following instructions are for apt-based distributions)
   - `sudo apt update`
   - `sudo apt install python3-pip`
 - `python3 -m pip install -r requirements.txt`
 - Start with: `python3 zeronet.py`
 - Open the ZeroHello landing page in your browser by navigating to: http://127.0.0.1:43110/

## Текущие ограничения

* Файловые транзакции не сжаты
* Нет приватных сайтов
* ...

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

Следующие шаги: [ZeroNet Developer Documentation](https://zeronet.io/docs/site_development/getting_started/)


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

## Help this project stay alive

### Become a maintainer

We need more maintainers! Become one today! Seriously, there's not going to be
that much new code to audit and auditing new code is the only requirement.

### Use it and spread the word

Make sure to tell people why do you use 0net and this fork in particular! People
need to know their alternatives.

### Financially support maintainers

Currently the only maintainer of this fork is @caryoscelus. You can see ways to
donate to them on https://caryoscelus.github.io/donate/

If you want to make sure your donation is recognized as donation for this
project, there is a dedicated bitcoin address for that, too:
1Kjuw3reZvxRVNs27Gen7jPJYCn6LY7Fg6

If you want to donate in a different way, feel free to contact maintainer or
create an issue
