# Skills

A collection of Claude Code agent skills I've built across different projects, kept here as a portfolio of what agent skills can do.

## petroleum-jobs

A three-step Rigzone scraping pipeline. `rigzone-scrape-job-post-urls` walks the paginated search listing on rigzone.com and collects job posting URLs into a pending queue. `rigzone-read-one-post` takes one URL from that queue, handles the tab-hidden description on the posting page, and saves the post as a structured markdown file. `rigzone-normalize-job-post-to-json` then turns that raw markdown into a display-ready JSON job post — deriving uids, slugs, and location fields mechanically, and normalizing content like titles, description summaries, benefits, salary, and certifications.

## airport-jobs

Two skills serving an Express.js MVC site for airport jobs. `job-post-scraper` takes a job posting URL or pasted description text and converts it into a structured JSON file. `categorize-job-post` then assigns a category to that structured post so it fits the site's taxonomy.

## nodejs-architecture

A standalone reference skill for designing and refactoring Node.js backends as modular, plug-and-play systems. It guides decisions about feature modules, dependency injection, a plugin registry, domain events, and ports/adapters — where code should live, when to make a feature swappable, and whether to use a direct call or an event.
