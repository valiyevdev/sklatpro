What is a card in web design?

A card is a self-contained UI component that groups related information — typically an image, title, description, and action — into a visually distinct container. Cards are used for blog listings, product grids, team members, testimonials, pricing plans, and any content that benefits from a consistent visual grouping pattern.

What makes a good website card design?

Clear visual hierarchy within the card (what to look at first, second, third), sufficient padding to avoid a cramped feeling, a clear single action (the card should do one thing), and visual consistency across the set of cards. Bad cards try to communicate too many things and fail at all of them.

How much padding should a website card have?

More than you think. 24px minimum internal padding for desktop cards, 20px for mobile. Cards that feel cramped almost always have too little padding — the content needs breathing room inside the container, especially if there's a border or shadow defining the card boundary.

Cards are everywhere on the modern web.

Blog post listings, product grids, service offerings, team member profiles, testimonials, pricing plans — the card pattern shows up in nearly every website. It is simultaneously the most useful and most abused UI component in web design.

Done well, cards create scannable, organised content that guides visitors efficiently. Done poorly, they feel crowded, inconsistent, and cheap.

What Is a Card and When Should You Use One?
A card is a self-contained content container. It groups related information and presents it as a discrete unit — visually separated from adjacent cards.

Use cards when:

You have multiple items of the same type (blog posts, products, team members)
Each item has similar attributes (image + title + description + link)
Users need to scan and compare items
The content works as a grid or collection
Do not use cards when:

You only have one or two items — a card for a single item is just a styled box
The content is flowing editorial text — cards interrupt reading flow
The hierarchy doesn't fit the card model — not all content has an image + title + body
The Anatomy of a Well-Designed Card
Every effective card has the same underlying structure:

1. Container — the visual boundary of the card. Can be defined by a border, background colour change, shadow, or spacing alone.

2. Media (optional) — image, video thumbnail, or icon at the top. Sets the visual tone and helps scanning.

3. Primary content — title or headline. This is the most important text in the card and should have the strongest visual weight.

4. Secondary content — description, excerpt, or supporting details. Lighter weight, smaller size.

5. Metadata — date, category, author, price, rating. Supporting context, typically smallest and lightest.

6. Action — the call to action. Can be a button, a link, or the entire card itself being clickable.

Feature
Weak Card Design
Strong Card Design
Padding
8–12px (cramped)
24–32px (breathing room)
Title weight
Same as body text
Clearly heavier — the first thing scanned
Action
Unclear or multiple CTAs
One clear action per card
Image aspect ratio
Variable (inconsistent grid)
Fixed aspect ratio across the set
Card height
Variable (ragged grid)
Equal height with aligned bottoms
Hover state
No feedback
Subtle elevation or border change
Card Layout Patterns
The Standard Content Card
The workhorse of the web. Image on top, title, description, metadata, and link below.

Works for: blog posts, articles, case studies, portfolio items.

Key design decisions:

Fix the image aspect ratio (16:9 or 3:2 are typical)
Keep description to 2–3 lines — truncate with line-clamp if needed
Make the entire card clickable, not just the title
The Horizontal Card
Image on the left, content on the right. Works better for dense information lists.

Works for: search results, product listings, news feeds.

Key design decisions:

Image should be roughly square or portrait — wide images look odd horizontal
Content needs enough space — don't make the image too large on mobile
The Compact Card
No image, just title + description + metadata. More information-dense.

Works for: documentation links, feature lists, comparison sets.

Key design decisions:

Relies entirely on typography for hierarchy — get the type scale right
Icon can substitute for image to add visual variety
The Feature Card
One large, prominent card — used to highlight a single important item.

Works for: featured blog post, hero testimonial, primary product.

Key design decisions:

Must be visually distinct from regular cards in the grid
Typically spans 2 columns or has larger image treatment
Card Spacing and Padding
Padding is where most card designs fail.

The internal padding — between the card boundary and the content — determines whether a card feels professional or cheap. Too little padding and the content feels trapped inside the container.

Recommended padding values:

Desktop cards: 24–32px all sides
Mobile cards: 20–24px all sides
Cards with images: 0 padding on image (full bleed), 20–28px on content area below
Gap between cards in a grid:

Desktop: 24–32px gap
Mobile: 16–20px gap
Never less than 16px — cards need to breathe between them too
✦
Test Padding on Real Content

Design cards with real content, not placeholder text. Lorem ipsum doesn't expose padding problems — real titles of different lengths do. Always test with 3–4 word titles and 12–15 word titles to make sure both look good.

Card Borders, Shadows, and Elevation
How you define the card boundary sets the visual tone of the entire design.

Border only: A subtle 1px border in a light grey. Works for minimal, functional designs. Feels clean and flat.

Shadow only: A soft box shadow. Suggests the card is elevated off the page. Works for more layered, dimensional designs.

Border + shadow: Avoid combining both unless the design specifically calls for strong separation. Often feels heavy and overdone.

Background colour change: The card has a different background from the page. Can work without border or shadow. Clean and modern.

No boundary: Cards in a tight grid can sometimes be defined purely by spacing and alignment, with no visual boundary. Works only when the grid structure is very clear.

Card Hover States
Cards almost always benefit from a hover state — visual feedback that confirms the card is interactive.

Effective hover patterns:

Subtle elevation: Increase box-shadow on hover (transition: box-shadow 200ms ease)
Border accent: Add or change a border colour on hover
Image scale: Slight zoom on the card image (transform: scale(1.02))
Title colour change: Change the title colour to the brand colour
Underline reveal: Show underline on title text on hover
Avoid hover states that move the entire card (it shifts the layout and disorients users). Keep hover transitions short — 150–200ms feels responsive without being abrupt.

Equal-Height Cards
One of the most common card grid problems: cards of different heights.

When card content varies — some descriptions are long, some are short — the grid becomes ragged. This looks like poor design, even when the individual cards are well-crafted.

Solutions:

CSS Grid with align-items: stretch on the grid container
Fixed description height with overflow: hidden and line-clamp
Action button at bottom of card, pinned with flexbox (flex-direction: column; justify-content: space-between)
The pinned action pattern — where the CTA button always sits at the bottom regardless of content length — is the most robust solution for mixed-length content.

Cards on Mobile
Cards designed for desktop grids need to work on mobile too.

Mobile card patterns:

Single column stack (most common and most reliable)
Horizontal scroll carousel (works for featured items, not for primary content grids)
Compact 2-column grid (works only for very simple cards with short titles)
For most sites, a 3-column desktop grid should collapse to 2 columns at tablet and 1 column at mobile. The padding inside cards should reduce slightly on mobile, but never below 20px.

⚠
Horizontal Scroll Cards on Mobile

Horizontal swipe carousels of cards are popular but problematic. They hide content, require users to discover the swipe gesture, and often show partial cards that look unfinished. Use them only for supplementary content — never for primary information a user needs to find.

Blog Post Cards
Blog cards are the most common card pattern and deserve specific attention.

Essential elements:

Category tag or label (helps scanning and filtering)
Title — 2–3 lines maximum before truncation
Excerpt — optional but useful for posts where the title isn't self-explanatory
Date and/or author
Read time estimate
Optional but valuable:

Featured image (adds visual variety to the grid)
Author avatar for personal brands
Read website blog design guide for the complete approach to blog page layout and card design.

Website that needs better card design and layout?

Evoke Studio designs Next.js websites with precise, professional UI — card grids, blog layouts, portfolio pages, and complete site design. Packages from $1,500.

Start Your Web Project
View Services & Pricing

How many cards should appear in a row on desktop?
+
Two to four cards per row is the effective range for most content types. Three is the most common and usually works best — it creates a balanced grid without making individual cards too narrow. Four-column grids work for compact content (products, icons) but feel crowded for editorial content. Two-column grids are better for content with more detail or longer descriptions.


Should cards always have images?
+
No — cards work well without images when the typography hierarchy is strong. Feature lists, service cards, documentation links, and comparison cards often work better without images. Images add visual variety but also add complexity: they need consistent aspect ratios, quality photography, and careful treatment on mobile. Only add images when they genuinely add information value.


What is the correct card border radius?
+
Depends on the overall design aesthetic. 0px (sharp corners) for technical, editorial, or premium minimal designs. 4–8px for most professional sites — subtle rounding without looking rounded. 12–16px for friendly, consumer-facing, or app-like designs. Match the border radius of your cards to the border radius used elsewhere in your UI — consistency matters more than the specific value.


How do I make all cards the same height?
+
Use CSS Grid with `align-items: stretch` on the grid container, and make each card a `display: flex; flex-direction: column`. Then use `margin-top: auto` or `flex-grow: 1` on the content area above the action button to push the button to the bottom. This creates equal-height cards regardless of content length, with the action always at the bottom — the cleanest solution.


How do I design accessible cards?
+
Make the entire card clickable via a single `<a>` tag (not multiple links within the card). Use `aria-label` on the link to describe the destination ('Read article: [title]'). Ensure hover states have visible focus states too (`:focus-visible`). Avoid using `div` onClick — use semantic `<a>` or `<button>` elements. Maintain sufficient colour contrast for all text in the card, including secondary text on light backgrounds.