# ZeroNet [![Build Status](https://travis-ci.org/HelloZeroNet/ZeroNet.svg?branch=py3)](https://travis-ci.org/HelloZeroNet/ZeroNet) [![Documentation](https://img.shields.io/badge/docs-faq-brightgreen.svg)](https://zeronet.io/docs/faq/) [![Help](https://img.shields.io/badge/keep_this_project_alive-donate-yellow.svg)](https://zeronet.io/docs/help_zeronet/donate/) ![tests](https://github.com/HelloZeroNet/ZeroNet/workflows/tests/badge.svg) [![Docker Pulls](https://img.shields.io/docker/pulls/nofish/zeronet)](https://hub.docker.com/r/nofish/zeronet)

Sites descentralizados usando criptografia Bitcoin e a rede BitTorrent - https://zeronet.io / [onion](http://zeronet34m3r5ngdu54uj57dcafpgdjhxsgq5kla5con4qvcmfzpvhad.onion)


## Por quê?

* Acreditamos na rede e na comunicação aberta, livre e sem censura.
* Não há um único ponto de falha: O site permanece online enquanto pelo menos 1 colega o estiver servindo.
* Sem custos de hospedagem: Os sites são servidos por visitantes.
* Impossível de ser desligado: Não está em lugar nenhum porque está em toda parte.
* Rápido e funciona offline: Você pode acessar o site mesmo que a Internet não esteja disponível.


## Características
* Sites atualizados em tempo real
* Suporte a domínios .bit Namecoin
* Fácil de configurar: desempacotar e executar
* Clonar websites em um clique
* Sem senha [BIP32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki)
 autorização baseada: Sua conta é protegida pela mesma criptografia de sua carteira de Bitcoin
* Servidor SQL embutido com sincronização de dados P2P: Permite um desenvolvimento mais fácil do site e tempos de carregamento de página mais rápidos
* Anonimato: Suporte completo de rede Tor com serviços ocultos .onion ao invés de endereços IPv4
* Conexões criptografadas TLS
* Abertura automática da porta uPnP
* Plugin para suporte multiusuário (openproxy)
* Funciona com qualquer navegador/OS


## Como funciona?

* Após iniciar o 'zeronet.py' você poderá visitar os sites da zeronet utilizando
'http://127.0.0.1:43110/{zeronet_address}' (eg.
'http://127.0.0.1:43110/1HeLLo4uzjaLetFx6NH3PMwFP3qbRbTf3D').
 
* Quando você visita um novo site zeronet, ele tenta encontrar pares usando a rede BitTorrent para poder baixar os arquivos do site (html, css, js...) a partir deles.
* Cada site visitado também é servido por você.
* Cada site contém um arquivo 'content.json' que contém todos os outros arquivos em um hash sha512 e uma assinatura gerada utilizando a chave privada do site.
* Se o proprietário do site (que tem a chave privada para o endereço do site) modificar o site, então ele assina o novo 'content.json' e o publica para os colegas. Posteriormente, os 'peers' verificam a integridade do 'content.json' (utilizando a assinatura), fazem o download dos arquivos modificados e publicam o novo conteúdo para outros colegas.

#### [Slideshow sobre criptografia ZeroNet, atualizações de sites, sites multiusuário »](https://docs.google.com/presentation/d/1_2qK1IuOKJ51pgBvllZ9Yu7Au2l551t3XBgyTSvilew/pub?start=false&loop=false&delayms=3000)
#### [Perguntas mais frequentes »](https://zeronet.io/docs/faq/)

#### [ZeroNet Developer Documentation »](https://zeronet.io/docs/site_development/getting_started/)


## Capturas de tela

![Screenshot](https://i.imgur.com/H60OAHY.png)
![ZeroTalk](https://zeronet.io/docs/img/zerotalk.png)

#### [Mais screenshots nos documentos da ZeroNet »](https://zeronet.io/docs/using_zeronet/sample_sites/)


## Como aderir

### Windows

- Download [ZeroNet-py3-win64.zip](https://github.com/HelloZeroNet/ZeroNet-win/archive/dist-win64/Zer oNet-py3-win64.zip) (18MB)
- Descompactar em qualquer lugar
- Executar 'ZeroNet.exe' 

### macOS

- Download [ZeroNet-dist-mac.zip](https://github.com/HelloZeroNet/ZeroNet-dist/archive/mac/ZeroNet-di st-mac.zip) (13.2MB)
- Descompactar em qualquer lugar
- Executar 'ZeroNet.app' 


### Linux (x86-64bit)
- 'wget https://github.com/HelloZeroNet/ZeroNet-linux/archive/dist-linux64/ZeroNet-py3-linux64.tar.gz'
- 'tar xvpfz ZeroNet-py3-linux64.tar.gz'
- 'cd ZeroNet-linux-dist-linux64/'
- Comece com: './ZeroNet.sh'
- Abra a página de destino ZeroHello no seu navegador, navegando para: http://127.0.0.1:43110/

__Dica:__ Comece com './ZeroNet.sh --ui_ip '*' --ui_restrict seu.ip.address' para permitir conexões remotas na interface web.

#### Android (braço, braço64, x86)
- versão mínima compatível com Android 16 (JellyBean)
- [<img src="https://play.google.com/intl/en_us/badges/images/generic/en_badge_web_generic.png" 
      alt="Download pelo Google Play" 
      height="80">](https://play.google.com/store/apps/details?id=in.canews.zeronetmobile)
- APK download: https://github.com/canewsin/zeronet_mobile/releases
- XDA Labs: https://labs.xda-developers.com/store/app/in.canews.zeronet

#### Docker
Há uma imagem oficial, construída a partir da fonte em: https://hub.docker.com/r/nofish/zeronet/ 

#### Instalar a partir da fonte

- 'wget https://github.com/HelloZeroNet/ZeroNet/archive/py3/ZeroNet-py3.tar.gz'
- 'tar xvpfz ZeroNet-py3.tar.gz'
- 'cd ZeroNet-py3'
- 'sudo apt-get update'
- 'sudo apt-get install python3-pip'
- 'sudo python3 -m pip install -r requirements.txt'
- Comece com: "python3 zeronet.py
- Abra a página de destino ZeroHello em seu navegador navegando para: http://127.0.0.1:43110/ 

## Limitações atuais

* ~~Nenhuma divisão de arquivo tipo torrente para suporte a arquivos grandes~~ (suporte a arquivos grandes adicionado)
* ~~Não mais anônimo do que Bittorrent~~ (suporte completo de Tor integrado adicionado)
* As transações de arquivos ainda não são compactadas ~~ ou criptografadas ~~ (criptografia TLS adicionada)
* Nenhum local privado


## Como posso criar um site ZeroNet?

* Clique em **⋮** > **"Criar site novo, vazio"** item de menu no site [ZeroHello](http://127.0.0.1:43110/1HeLLo4uzjaLetFx6NH3PMwFP3qbRbTf3D).
* Você será **realizado** para um site completamente novo que só pode ser modificado por você! 
* Você pode encontrar e modificar o conteúdo de seu site no diretório **dados/[endereço de seu site]**.
* Após as modificações abrir seu site, arraste o botão superior direito "0" para a esquerda, depois pressione **sign** e **publish** buttons on the bottom

Próximos passos: [Documentação do Desenvolvedor da ZeroNet](https://zeronet.io/docs/site_development/getting_started/)

## Ajude a manter este projeto vivo

- Bitcoin: 1QDhxQ6PraUZa21ET5fYUCPgdrwBomnFgX
- Paypal: https://zeronet.io/docs/help_zeronet/donate/ 

#### Patrocinadores

* Melhor compatibilidade macOS/Safari possibilitada pelo [BrowserStack.com](https://www.browserstack.com)

#### Obrigado!

* Mais informações, ajuda, changelog, zeronet sites: https://www.reddit.com/r/zeronet/
* Venha, converse conosco: [#zeronet @ FreeNode](https://kiwiirc.com/client/irc.freenode.net/zeronet) ou em [gitter](https://gitter.im/HelloZeroNet/ZeroNet)
* Email: hello@zeronet.io (PGP: [960F FF2D 6C14 5AA6 13E8 491B 5B63 BAE6 CB96 13AE](_COPY13@zeronet.io_pub.asc))
