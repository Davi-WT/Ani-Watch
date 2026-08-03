# Ani-Watch

Interface gráfica em Python para pesquisar e assistir animes usando o
[`ani-cli`](https://github.com/pystardust/ani-cli). Na primeira execução, o
programa instala automaticamente o script oficial em `~/.local/bin/ani-cli`
caso ele não esteja disponível.

## Executar

```bash
cd Ani-Watch
python3 -m pip install -r requirements.txt
python3 ani_watch.py
```

Em distribuições que fornecem o PyQt pelo gerenciador de pacotes, também é
possível instalar `python-pyqt6` (Arch/CachyOS) ou `python3-pyqt6` (Debian e
derivadas). A interface também aceita uma instalação existente do PyQt 5.

O `ani-cli` também precisa de `curl`, `grep`, `sed`, `fzf` e de um player
(`mpv` ou `vlc`). Para downloads, instale `yt-dlp` ou `ffmpeg`. A situação de
cada dependência aparece no rodapé do aplicativo.

## Recursos

- instalação e atualização do `ani-cli` sem `sudo`;
- busca visual e seleção de episódios;
- qualidade automática ou de 360p a 1080p;
- reprodução legendada/dublada com MPV ou VLC;
- detecção do fechamento do player para liberar o próximo episódio;
- download de episódios;
- painel com a saída e os erros do `ani-cli`.

O conteúdo é obtido pelos serviços usados pelo projeto original. Respeite as
leis locais e os direitos dos titulares do conteúdo.
