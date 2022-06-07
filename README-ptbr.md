# zeronet-conservancy

[in English](README.md) | [по-русски](README-ru.md) | [简体中文](README-zh-cn.md)

zeronet-conservancy é um garfo/continuação do projeto [ZeroNet](https://github.com/HelloZeroNet/ZeroNet)
(que foi abandonada por seu criador) que se dedica a sustentar a rede p2p existente e a desenvolver
seus valores de descentralização e liberdade, enquanto muda gradualmente para uma rede mais bem projetada

## Por que garfo?

Durante a crise da onion-v3, precisávamos de um garfo que funcionasse com onion-v3 e não dependesse da confiança de um ou
duas pessoas. Este garfo começou a partir do cumprimento dessa missão, implementando mudanças mínimas para
[ZeroNet/py3](https://github.com/HelloZeroNet/ZeroNet/tree/py3) ramo que é fácil de ser auditado por qualquer pessoa. Enquanto
você ainda pode usar as primeiras liberações do garfo para fazer funcionar a onion-v3, o objetivo deste garfo mudou desde então
e nos dedicamos a resolver mais problemas e melhorar a experiência do usuário e a segurança por toda parte, até 
a nova rede, completamente transparente e auditada está pronta e este projeto pode ser colocado para descansar

## Por que 0net?

* Acreditamos em redes e comunicação abertas, livres e não censuradas.
* Nenhum ponto único de falha: O site permanece online desde que pelo menos 1 par seja
  servindo-o.
* Sem custos de hospedagem: Os sites são servidos por visitantes.
* Impossível de ser desligado: Não está em lugar nenhum porque está em toda parte.
* Rápido e funciona offline: Você pode acessar o site, mesmo que a Internet seja
  indisponível.


## Características

 * Sites atualizados em tempo real
 * Clonar websites em um clique
 * Autorização sem senha usando chaves públicas/privadas
 * Servidor SQL integrado com sincronização de dados P2P: permite um desenvolvimento dinâmico mais fácil do site
 * Anonimato: Suporte de rede Tor com serviços ocultos .onion (incluindo suporte a onion-v3)
 * conexões criptografadas TLS (através de clearnet)
 * Abertura automática da porta uPnP (se optado por entrar)
 * Plugin para suporte multiusuário (openproxy)
 * Funciona com qualquer navegador/OS moderno


## Como funciona?

* Após iniciar o `zeronet.py` você poderá visitar os sites da zeronet utilizando
  `http://127.0.0.1:43110/{zeronet_address}` (ex.
  `http://127.0.0.1:43110/126NXcevn1AUehWFZLTBw7FrX1crEizQdr`).
* Quando você visita um novo site zeronet, ele tenta encontrar pares usando o BitTorrent
  para poder baixar os arquivos do site (html, css, js...) a partir deles.
* Cada site visitado também é servido por você.
* Cada site contém um arquivo `content.json` que contém todos os outros arquivos em um hash sha512
  e uma assinatura gerada usando a chave privada do site.
* Se o proprietário do site (que tem a chave privada para o endereço do site) modificar o
  então ele assina o novo `content.json` e o publica para os colegas.
  Em seguida, os pares verificam a integridade do `content.json` (utilizando o
  assinatura), eles baixam os arquivos modificados e publicam o novo conteúdo para
  outros colegas.

Os links a seguir referem-se à ZeroNet original:

- [Slideshow sobre criptografia ZeroNet, atualizações de sites, sites multiusuário "](https://docs.google.com/presentation/d/1_2qK1IuOKJ51pgBvllZ9Yu7Au2l551t3XBgyTSvilew/pub?start=false&loop=false&delayms=3000)
- [Perguntas mais freqüentes "](https://zeronet.io/docs/faq/)
- [Documentação do Desenvolvedor da ZeroNet "](https://zeronet.io/docs/site_development/getting_started/)

## Como aderir

### Instalar a partir da fonte (recomendado)

#### Dependências do sistema

##### Genéricos unix-like (incluindo mac os x)

Instalar o autoconf e outras ferramentas básicas de desenvolvimento, python3 e pip.

##### Apt-based (debian, ubuntu, etc)
 - `sudo apt update`
 - `sudo apt install pkg-config python3-pip python3-venv`

##### Android/Termux
 - install [Termux](https://termux.com/) (no Termux você pode instalar pacotes via `pkg install <nomes de pacotes>`)
 - Atualização do "pkg".
 - Pkg install python automake git binutils" (TODO: verificar nova instalação se há mais dependências para instalar)
 - (opcional) `pkg install tor`
 - (opcional) rodar tor via comando `tor --ControlPort 9051 --CookieAuthentication 1` (você pode então abrir uma nova sessão deslizando para a direita)

#### Construindo dependências python & running
 - clonar este repo (NOTA: no Android/Termux você deve cloná-lo na pasta "home" do Termux, porque o ambiente virtual não pode viver no `storage/`)
 - "python3 -m venv venv" (fazer python ambiente virtual, o último `venv` é apenas um nome, se você usar diferente você deve substituí-lo em comandos posteriores)
 - "fonte venv/bin/activate" (activar ambiente)
 - `python3 -m pip install -r requirements.txt` (instalar dependências)
 - zeronet.py` (**run zeronet-conservancy!**)
 - abra a página de desembarque em seu navegador navegando para: http://127.0.0.1:43110/
 - para reiniciá-lo a partir de um terminal novo, você precisa navegar para redirecionar o diretório e:
 - "fonte venv/bin/activate
 - "python3 zeronet.py

#### Construir imagem do Docker
- construir imagem 0net: `docker build -t 0net:conservancy . -f Dockerfile`
- ou construir imagem 0net com tor integrado: `docker build -t 0net:conservancy . -f Dockerfile.integrated_tor`
- e dirigi-lo: `docker run --rm -it -v </path/to/0n/data/directório>:/app/data -p 43110:43110 -p 26552:26552 0net:conservancy''.
- /caminho/até/0n/dados/diretório - diretório, onde todos os dados serão salvos, incluindo seus certificados secretos. Se você executá-lo com o modo de produção, não remova esta pasta!
- ou você pode executá-lo com o docker-compose: `docker compose up -d 0net` sobe dois containers - 0net e tor separadamente.
- ou: "docker compose up -d 0net-tor" para rodar 0net e tor em um recipiente.

#### roteiro alternativo
 - após instalar as dependências gerais e clonagem repo (como acima), execute `start-venv.sh` que criará um ambiente virtual para você e instalará os requisitos python
 - mais roteiros de conveniência a serem adicionados em breve

## Limitações atuais

* As transações de arquivos não são comprimidas
* Sem sites privados
* Sem suporte de DHT
* Elementos centralizados como o zeroid (estamos trabalhando nisso!)
* Nenhuma proteção confiável contra spam (e nisto também)
* Não funciona diretamente do navegador (uma das principais prioridades para o futuro médio)
* Sem transparência de dados


## Como posso criar um site ZeroNet?

 Clique em **⋮*** > **"Criar site novo, vazio "** item do menu [página admin](http://127.0.0.1:43110/126NXcevn1AUehWFZLTBw7FrX1crEizQdr).
 * Você será **re-direcionado *** para um site completamente novo que só pode ser modificado por você!
 * Você pode encontrar e modificar o conteúdo de seu site no diretório **data/[endereço de seu site]**.
 * Após as modificações abrir seu site, arraste o botão superior direito "0" para a esquerda, depois pressione **sign** e **publish** botões na parte inferior

Próximos passos: [Documentação do Desenvolvedor da ZeroNet](https://zeronet.io/docs/site_development/getting_started/)

## Ajude este projeto a permanecer vivo

### Torne-se um mantenedor

Precisamos de mais mantenedores! Torne-se um hoje! Você não precisa saber como codificar,
há muito mais trabalho a ser feito.

### Corrigir bugs e adicionar recursos

Decidimos ir em frente e fazer uma web p2p perfeita, então precisamos de mais ajuda
implementando-o.

#### Faça seu site/bring seu conteúdo

Sabemos que a documentação está faltando, mas tentamos o melhor para apoiar qualquer um
que quer migrar. Não hesite em perguntar.

#### Use-o e espalhe a palavra

Certifique-se de dizer às pessoas por que você usa 0net e este garfo em particular! Pessoas
precisam conhecer suas alternativas.

### Mantenedores de suporte financeiro

Atualmente, o principal desenvolvedor/mantenedor deste garfo é @caryoscelus. Você pode
veja maneiras de doar para eles em https://caryoscelus.github.io/donate/ (ou verifique
sidebar se você estiver lendo isto no github para mais maneiras). À medida que nossa equipe cresce, nós
também criará contas de equipe em plataformas amigáveis de financiamento de multidões.

Se você quiser ter certeza de que sua doação é reconhecida como doação para isto
projeto, também há um endereço dedicado ao bitcoin para isso:
1Kjuw3reZvxRVNs27Gen7jPJYCn6LY7Fg6

Se você quiser doar de uma maneira diferente, sinta-se à vontade para contatar o mantenedor ou
criar uma publicação!