# YouTube: title, description, upload settings

The film on YouTube: https://www.youtube.com/watch?v=WGMhXgNOMvQ

Everything to fill in when uploading `film/a_bunch_of_rocks.mp4`. The English text is the video's own; the German text
goes in YouTube Studio under **Languages → Add language → German** (title and description), so German viewers see it.
Chapter times follow from shots.yaml: `python -m rocks.shots` prints them, and a test fails when they are out of date.
The GitHub project (https://github.com/s-macke/A-Bunch-of-Rocks) is linked in the first lines of each description:
YouTube shows only those above "…more".
Copy only what is inside the code blocks. YouTube takes title and description as plain text: no Markdown (no bold,
no headings, no link syntax), but it turns URLs into links, timestamps into chapters and #words into hashtags.

## Files

| What | File | Where in YouTube Studio |
|---|---|---|
| Video (English audio) | `film/a_bunch_of_rocks.mp4` | Upload |
| Thumbnail (1280×720) | `film/a_bunch_of_rocks.thumbnail.png` (`scripts/thumbnail.py`) | Details → Thumbnail |
| German audio | `film/a_bunch_of_rocks.de.m4a` | Languages → German → Dub |
| Subtitles | `film/a_bunch_of_rocks.en.srt`, `film/a_bunch_of_rocks.de.srt` | Subtitles → Add language → Upload file (with timing) |

## English

**Title**

```
A Bunch of Rocks – xkcd 505, animated
```

**Description**

```
A man is stuck in an endless desert with infinite time. So he starts laying rocks in rows – and builds a computer.
And on that computer: a universe. Maybe ours.

Made entirely from code with Claude Code. How it was made, and the code to build it yourself:
https://github.com/s-macke/A-Bunch-of-Rocks

An animated adaptation of xkcd #505 "A Bunch of Rocks" by Randall Munroe.
The comic: https://xkcd.com/505/

Audio: English, and German (Deutsch) via the audio track menu. Subtitles in both languages.

Chapters
0:00 Cold open
0:15 Loneliness & discovery
1:48 The computer
3:18 Universe
4:32 Our world
5:31 Credits

How it was made: the whole film – animation, narration, music and sound – was made with Claude Code (Claude Opus 5.5)
from code, with no animation software. Narration, music and sound effects are AI-generated with ElevenLabs.
Code and making-of: https://github.com/s-macke/A-Bunch-of-Rocks (MIT for the code, CC BY-NC 4.0 for the film)

Credits
Story: xkcd #505 by Randall Munroe, CC BY-NC 2.5 (https://xkcd.com/license.html)
Font: xkcd Script (github.com/ipython/xkcd-font), CC BY-NC 3.0
Narration: "Drew" voice, ElevenLabs · Music and sound: generated with ElevenLabs

A non-commercial fan adaptation. Not affiliated with xkcd.
```

## Deutsch

**Titel**

```
A Bunch of Rocks – xkcd 505 als Kurzfilm
```

**Beschreibung**

```
Ein Mann sitzt in einer endlosen Wüste fest, mit unendlich viel Zeit. Also legt er Steine in Reihen – und baut einen
Computer. Und auf diesem Computer: ein Universum. Vielleicht unseres.

Komplett aus Code entstanden, mit Claude Code. Wie er gemacht wurde, und der Code zum Selberbauen:
https://github.com/s-macke/A-Bunch-of-Rocks

Eine animierte Umsetzung von xkcd #505 „A Bunch of Rocks“ von Randall Munroe.
Der Comic: https://xkcd.com/505/

Ton: Deutsch und Englisch (über das Tonspur-Menü). Untertitel in beiden Sprachen.

Kapitel
0:00 Prolog
0:15 Einsamkeit und Entdeckung
1:48 Der Computer
3:18 Das Universum
4:32 Unsere Welt
5:31 Abspann

Wie er entstanden ist: Der ganze Film – Animation, Sprecher, Musik und Ton – wurde mit Claude Code (Claude Opus 5.5)
aus Code erzeugt, ohne Animationsprogramm. Sprecher, Musik und Geräusche sind KI-generiert mit ElevenLabs.
Code und Making-of: https://github.com/s-macke/A-Bunch-of-Rocks (MIT für den Code, CC BY-NC 4.0 für den Film)

Credits
Geschichte: xkcd #505 von Randall Munroe, CC BY-NC 2.5 (https://xkcd.com/license.html)
Schrift: xkcd Script (github.com/ipython/xkcd-font), CC BY-NC 3.0
Sprecher: Stimme „Drew“, ElevenLabs · Musik und Geräusche: generiert mit ElevenLabs

Eine nicht-kommerzielle Fan-Adaption. Keine Verbindung zu xkcd.
```

## Upload settings

- **Video language:** English. **Title and description language:** English (German added under Languages).
- **Audience:** not made for kids.
- **Category:** Film & Animation. In the upload dialog it is hidden: Details → **Show more** (at the bottom) → Category.
  For all future uploads: Settings → Upload defaults → Advanced settings → Category.
- **License:** Standard YouTube License. Not "Creative Commons – Attribution": that license allows commercial reuse,
  which the comic's and the font's licenses (NC, non-commercial) do not allow us to grant.
- **Monetization:** off (the licenses are non-commercial).
- **AI use** (Altered or synthetic content): answer **No**. None of the four cases applies: no real person is made
  to say or do anything (the voice is a stock ElevenLabs voice, not an imitation of a real person), no real event or
  place is altered, nothing looks realistic (it is a stick-figure cartoon), and the AI-generated music is a
  background score, not the main focus of the video. The description says that voice, music and sound are
  AI-generated.
- **Tags:** xkcd, xkcd 505, A Bunch of Rocks, Randall Munroe, animation, short film, cellular automaton, Rule 110,
  simulation hypothesis, Claude Code.
