# Ani-Watch

Interface gráfica para pesquisar e assistir animes usando o
[`ani-cli`](https://github.com/pystardust/ani-cli). Os executáveis distribuídos
já incluem o Python e o Qt, portanto o usuário final não precisa instalar o
Python.

## Usar o executável

Baixe o artefato correspondente na execução mais recente de **Build
executables**, na aba **Actions** do GitHub:

- `Ani-Watch-Linux-x86_64`: extraia o `.tar.gz` e execute `Ani-Watch`;
- `Ani-Watch-Windows-x86_64`: extraia o `.zip` e execute `Ani-Watch.exe`.

O frontend é autossuficiente, mas o `ani-cli` e o player continuam sendo
programas externos:

- no Linux, instale `curl`, `grep`, `sed`, `fzf` e `mpv` ou `vlc`. Na primeira
  execução, o Ani-Watch instala o script oficial em `~/.local/bin/ani-cli`;
- no Windows, instale o `ani-cli` pelo Scoop (`scoop install ani-cli`), mantenha
  o Git Bash e o `fzf` no `PATH`, e instale `mpv` ou `vlc`. O botão **Como
  instalar** também mostra essa orientação.

Para downloads, instale ainda `yt-dlp` ou `ffmpeg`.

## Executar pelo código-fonte

```bash
cd Ani-Watch
python3 -m pip install -r requirements.txt
python3 ani_watch.py
```

Em distribuições que fornecem o PyQt pelo gerenciador de pacotes, também é
possível instalar `python-pyqt6` (Arch/CachyOS) ou `python3-pyqt6` (Debian e
derivadas). A interface também aceita uma instalação existente do PyQt 5.

## Gerar os executáveis

O computador usado para compilar precisa ter Python; o computador do usuário
final não. O PyInstaller precisa gerar cada pacote dentro do próprio sistema
operacional:

```bash
./build_linux.sh
```

No Windows, execute:

```bat
build_windows.bat
```

O resultado é criado em `dist/`. O workflow
`.github/workflows/build-executables.yml` executa os dois builds em máquinas
Windows e Linux e publica os pacotes como artefatos.

## Recursos

- instalação e atualização do `ani-cli` sem `sudo`;
- busca visual e seleção de episódios;
- qualidade automática ou de 360p a 1080p;
- preferência de legenda em português ou inglês;
- reprodução legendada/dublada com MPV ou VLC;
- detecção do fechamento do player para liberar o próximo episódio;
- download de episódios;
- painel com a saída e os erros do `ani-cli`.

A preferência de idioma funciona quando o vídeo oferece faixas de legenda
separadas. Se a fonte trouxer a legenda gravada na imagem, o player não poderá
trocar seu idioma.

O conteúdo é obtido pelos serviços usados pelo projeto original. Respeite as
leis locais e os direitos dos titulares do conteúdo.
