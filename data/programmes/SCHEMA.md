# Programme extraction schema (one JSON file per festival year)

Input: ~/tmp/mvff/raw/text/<YEAR>.txt — the year's printed Mill Valley Film Festival programme (from the PDF
archived in the Wayback Machine), split by `=== PAGE n ===` markers (n = PDF page number).
Output: ~/tmp/mvff/data/programmes/<YEAR>.json (UTF-8, pretty-printed, valid JSON)

{
  "year": 2006,
  "edition": 29,                               // "29th Mill Valley Film Festival" -> 29, null if not printed
  "dates": "October 5-15, 2006",               // as printed
  "source_pdf": "<the PDF filename you were given>",
  "venues": [{"name": "Sequoia Theatre", "address": "25 Throckmorton Ave, Mill Valley"}],
  "sections": ["Valley of the Docs", "5@5 Shorts", "Children's FilmFest", ...],   // programme sections as printed
  "films": [{
      "title": "Babel",                        // proper title case, not ALL CAPS
      "original_title": null,                  // if a second (original-language) title is printed
      "directors": ["Alejandro González Iñárritu"],
      "countries": ["USA", "Mexico"],          // as printed, [] if absent
      "film_year": 2006,                       // production year, null if absent
      "runtime_min": 142,                      // null if absent
      "language": null,                        // as printed, null if absent
      "section": "Gala",                       // the programme section it is listed under, null if unclear
      "slot": "Opening Night",                 // Opening Night / Closing Night / Centerpiece / Tribute / Spotlight / Gala, else null
      "premiere": "US Premiere",               // as printed, null
      "is_short": false,                       // true for shorts (usually < 40 min, or listed in a shorts programme)
      "shorts_program": null,                  // name of the shorts programme it screened in
      "guests": ["Alejandro González Iñárritu"], // people named as attending ("in person", "director expected"), [] if none
      "screenings": [{"date": "2006-10-05", "time": "7:00 PM", "venue": "Sequoia"}],   // ISO date when derivable
      "summary": "ONE sentence (max 30 words) in your own words saying what the film is about",
      "cast": ["Brad Pitt", "Cate Blanchett"], // principal cast if printed (max 6), [] if none
      "page": 23                               // the === PAGE n === where the film's entry is
  }],
  "events": [{                                 // tributes, spotlights, panels, seminars, music events, parties, awards nights
      "title": "Tribute to Annette Bening",
      "kind": "tribute|spotlight|panel|seminar|conversation|music|party|award|workshop|other",
      "date": "2006-10-08", "time": "7:00 PM", "venue": "...",
      "people": [{"name": "Annette Bening", "role": "honoree|moderator|panelist|speaker|performer|host"}],
      "related_films": ["Running with Scissors"],
      "summary": "ONE sentence in your own words",
      "page": 12
  }],
  "awards": [{"name": "...", "recipient": "...", "film": null, "page": 5}],   // only awards printed in this programme
  "staff": [{"name": "Mark Fishkin", "role": "Executive Director"}],          // festival staff/programmers if listed
  "notes": "anything odd: unreadable pages, sections skipped, uncertain readings, duplicate listings merged"
}

Rules
- Read the WHOLE file page by page (use offset/limit; it is long). Do not skim and do not stop early: every film
  in the programme must be in "films". Shorts in shorts programmes are films too (with shorts_program set).
- Do not invent anything. Every value comes from the programme text. Use null / [] for unknowns.
- "summary" is the one place you write your own words: one short factual sentence; never copy the programme's
  synopsis text.
- Names in normal capitalisation ("ANNETTE BENING" -> "Annette Bening"). Titles in proper title case.
- Layout text interleaves 2-4 columns; untangle carefully. The same film may appear in a schedule grid and in its
  own entry: one record per film, with all its screenings merged.
- Skip ads, sponsor lists, ticket/box-office information and letters (but take staff names if listed).
- Validate with: python3 -c "import json;json.load(open('<file>'))" and report counts (films, shorts, events).
