# Finding film posters (Mill Valley Film Festival Explorer)

Input: batchN-input.json — films that screened at the Mill Valley Film Festival (Marin County, California) between
2001 and 2026, with no poster found on English Wikipedia, Wikidata or the other-language Wikipedias. Mostly international and American independent
features and documentaries, some studio awards-season titles. Each entry has id, title, original_title, directors,
countries, film_year, festival year.

Goal: for as many films as possible, find the film's real poster (theatrical/festival one-sheet or official key art,
portrait orientation). Places to look (WebSearch / WebFetch / curl):
- MUBI and FilmAffinity film pages, Wikipedia in other languages (the original-language title), Wikimedia Commons
- Do NOT use TMDB (themoviedb.org) or Letterboxd: their robots.txt files exclude AI agents.
- the film's official website (og:image, press kit / EPK pages)
- distributors and sales agents (Sony Pictures Classics, IFC, Magnolia, Music Box, Kino Lorber, Film Movement,
  Strand, Zeitgeist, Oscilloscope, Neon, A24, Roadside, Janus, Cohen Media, Bleecker Street, Greenwich, Cinema Guild,
  Grasshopper, Cinedigm, Abramorama; international sales: The Match Factory, Wild Bunch, Celluloid Dreams, mk2,
  Memento, Pyramide, Films Boutique, Beta, Fortissimo, Visit Films, Cinephil, Dogwoof, Cat&Docs…)
- other festivals' film pages (Sundance, Toronto, Berlinale, Cannes, Venice, Telluride, SFFILM, Tribeca, SXSW, Hot
  Docs, IDFA, Rotterdam, Karlovy Vary, Busan, Locarno…) and national film institutes (unifrance, German Films,
  Swedish Film Institute, Danish Film Institute, Screen Australia, NZ Film Commission, Telefilm, IFI, Eye…)
- the Wayback Machine (web.archive.org) for official sites that have gone offline
- Do NOT use IMDb or Amazon image URLs (their terms forbid it).

Verify every hit: download the image (curl into your own scratch folder — use a folder named after your batch, e.g.
scratchpad/posters-batchN/, never a shared one) and LOOK at it with the Read tool. Accept it only if it is clearly
the poster/key art for THIS film (title on it matches, or the page is unambiguously this film by these directors,
and the year fits). A wide still is not a poster. Many films share titles: check the director. Short films often have
no poster: record nothing rather than guess.

Output: write batchN-output.json in this folder (valid JSON list), one entry per film you found:
  {"id": "<film id from input>", "title": "...", "image_url": "<direct URL of the image file>",
   "page_url": "<the page where you found it>", "source": "<short label, e.g. 'Official site', 'MUBI', 'Berlinale'>",
   "kind": "poster" | "key art", "confidence": "high" | "medium", "note": "optional"}
Prefer an image around 600–1000 px wide. Be gentle with sites: a second or so between requests to the same host.
Reply with: how many found of how many, and anything odd.
