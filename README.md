# Rentorium

**A Property Rental & Sales Platform** · Django 5, SQLite

🔗 **Live demo:** https://faiazpronoy.pythonanywhere.com · 📦 **[All versions](../../releases)**

| | |
|---|---|
| **v2.0** — current | Rebuilt solo: new interface, agent console, private ownership documents, 177 tests. |
| **v1.0** — [see release](../../releases/tag/v1.0) | The original CSE471 group submission at BRAC University, built on a Bootstrap template. |

**Try it:** sign in as a renter with `rafid@rentorium.test` / `Rentorium@2026`, or as the agent with `agent@rentorium.test` / `Agent@2026`.

---

A property rental and sales platform for Bangladesh: search listings, book a
viewing, message the owner, and let an agent keep the whole thing honest.

Django 5 and SQLite. Two Python dependencies, no build step, no front end
framework: the interface is hand written CSS and plain JavaScript, and every
icon is inline SVG. The only external request is the web font, which falls back
to a system serif and sans pair, so the site works the same offline.

---

## Running it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cd Rentorium
python manage.py migrate
python manage.py seed_demo       # fills it with realistic demo data
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

| Role | Sign in with |
|---|---|
| Agent | `agent@rentorium.test` / `Agent@2026` |
| Owner | `faiaz@rentorium.test` / `Rentorium@2026` |
| Renter | `rafid@rentorium.test` / `Rentorium@2026` |
| Django admin | `admin` / `Admin@2026` at `/admin/` |

`seed_demo` creates 11 live listings with photos, one waiting for approval, one
sent back for changes, plus reviews, bookings, conversations, saved properties
and contact enquiries, so every page has something real on it.

Settings that matter come from the environment: copy `.env.example` to `.env`
and fill it in. With no SMTP settings, mail is printed to the console, which is
what you want while marking.

---

## What it does

### For someone looking for a place

- **Search that means something.** Keyword, rent or buy, type, city, area, price
  range, minimum size, furnishing, bedrooms, bathrooms, business use, land type
  and amenities, with seven sort orders. Amenities combine with AND, not OR, so
  ticking two really does narrow it down.
- **Save a search** and come straight back to the same filters.
- **Save properties** to a shortlist, with the heart updating without a page reload.
- **Compare up to four side by side** on price, size, price per square foot,
  rooms, rating and amenity count.
- **Book a viewing.** Pick a date and time; the owner accepts, declines with a
  reason, or suggests another slot.
- **Message the owner** in a thread tied to that one property.
- **Review a place** you have seen. One review per person per property.

### For someone with a place to let

- **Guided listing flow**: pick residential, commercial or land, then fill in only
  the fields that type actually needs.
- **A photo gallery** of up to eight images, with a chosen cover photo.
- **A private document upload** for the ownership paper.
- **Your own dashboard**: views, saves, enquiries, visit requests, and a fourteen
  day view chart across every listing you own.
- **Per listing analytics**: a thirty day view chart, who saved it, how many
  enquiries and visits it produced.
- **Status control**: hide a listing, mark it rented or sold, or send it back
  into the queue.

### For the agent

- **An approval queue** with the photos, the description, the owner's history and
  the ownership paper all on one screen.
- **Approve, send back with a written reason, or withdraw an approval.** The owner
  is notified either way, and sees exactly what to fix.
- **Verify ownership papers**, which puts a verified badge on the owner.
- **Feature a listing** onto the front page.
- **Platform stats**: listings, users, views, bookings, enquiries, saves,
  ratings, a fourteen day view chart, a six month sign up chart, and breakdowns
  by type and by area.
- **A permanent decision log** and a user directory.
- **The contact form queue**, with replies that land in the person's notifications.

---

## What I fixed on the second pass

I came back to this after the course finished. Three access control checks were
missing, and each now has a test that fails if the check is removed again.

- **Anyone signed in could read anyone's ownership papers.** The check was
  `if request.user.UserProfile.is_agent or property_instance.user_id` — a
  primary key is always truthy, so the condition was always true. Permission
  now lives on the model in `can_documents_be_seen_by`, and the file itself is
  stored outside `MEDIA_ROOT` so it has no guessable URL.
- **Anyone signed in could edit or delete anyone's listing.** `update_property`
  and `delete_property` fetched the row by id and never asked whose it was.
- **Secrets were committed.** `settings.py` held a live Gmail app password and a
  Stripe key in plain text. Both now come from the environment. (If you are
  reading this from the old history: those credentials have been rotated.)

Other things that were broken:

- `LandProperty.Road_size_in_sqft = models.IntegerField` — no brackets, so the
  column was never created.
- The context processor called `.get()` with no guard, so a user without a
  profile row took the whole site down. A signal now creates profiles.
- `property_detail` passed `vars(instance)` into the template context.
- Agent decisions overwrote one text column, so the history was lost. Each
  decision is now its own `AgentAction` row.
- `ContactForm` was a `forms.Form` with a `Meta` pointing at a model, which does
  nothing, and the view read `request.POST` directly.
- Search paging repeated some listings and skipped others, because the filter
  form was only bound when the query string was non-empty.
- A cancelled viewing could be accepted again through the accept URL.
- The owner dashboard crashed on Windows: the chart labels used
  `strftime('%-d')`, which only exists on glibc.

---

## How it is kept safe now

- **Passwords** go through Django's hasher with the full validator set plus a
  house rule: eight characters, one capital, one small, one digit, one symbol.
- **Six wrong sign in attempts** lock an address for fifteen minutes, and every
  attempt is recorded and shown back to the user on their profile.
- **State changes go through POST**, with a `@post_required` decorator and
  Django's CSRF protection on the forms.
- **Authorisation lives on the model**, not scattered through the views:
  `can_be_seen_by`, `can_be_edited_by`, `can_documents_be_seen_by`.
- **The `next` parameter is checked** so a sign in link cannot bounce you to
  another site.
- **The search box cannot reach the ORM as a field name.** Every filter goes
  through a form first, so an unknown value simply does not filter.
- **The contact form has a honeypot** and real validation.
- **Uploads are limited** by size and by extension.

---

## The data model

Twenty models. The decisions worth explaining:

- **`AllProperty` with three subtypes.** Multi table inheritance:
  the shared columns live in one table, and residential, commercial and land
  each add their own. `listing.specific` returns whichever subtype row exists.
- **Money is `DecimalField`**, so a price is never quietly rounded.
- **One `status` field** instead of a free text `Approval_by_Agent` column and a
  `needs_approval` flag that could disagree with each other. `save()` keeps the
  two older columns in step so nothing that reads them breaks.
- **A database constraint stops double bookings.** Not a check in a view, an
  actual partial unique index:

```python
models.UniqueConstraint(
    fields=['property', 'visit_date', 'visit_time'],
    condition=Q(status='accepted'),
    name='one_accepted_visit_per_slot',
)
```

- **One review per person per property**, and **one saved copy per person per
  property**, both enforced by unique constraints rather than by hoping.
- **`PropertyView`** records one row per person per property per day, which is
  what makes the analytics charts mean anything.
- **Indexes** on status and date, type and listing intent, area and city, price
  and slug.

```
User 1───1 UserProfile
UserProfile 1───* AllProperty ───┬── ResidentialProperty
                                 ├── CommercialProperty
                                 └── LandProperty
AllProperty 1───* PropertyImage, PropertyReview, Booking, Conversation,
                   Favourite, PropertyView, AgentAction
AllProperty *───* Amenity
Conversation 1───* Message
UserProfile 1───* Notification, SavedSearch, LoginAttempt
```

---

## Layout

```
Rentorium/
├── manage.py
├── Rentorium/            settings, urls, wsgi, asgi
├── authentication/       profiles, roles, notifications, sign in log, guards
│   ├── decorators.py     login_required_message, agent_required, post_required
│   └── management/commands/seed_demo.py
├── property/             listings, search, images, favourites, reviews,
│                         bookings, messaging, saved searches, analytics
├── basic/                home, about, FAQs, terms, testimonials, contact
├── Agents/               approval queue, decision log, platform stats
├── templates/            43 pages plus shared partials
└── static/
    ├── css/app.css       the whole design system, light and dark
    └── js/app.js         plain JavaScript, no library
```

The four apps and the original URL names are kept, so old links still work.

---

## Tests

```bash
cd Rentorium
python manage.py test
```

**122 tests, all passing.** They cover:

- models: slugs, status transitions, price per square foot, subtype resolution,
  and the unique constraints
- access control, from both sides: a stranger is refused, the owner and the
  agent are let in — for documents, editing, deleting, conversations and the
  agent console
- private documents: the file has no public URL, and only the document view
  hands it over
- bookings: past dates, out of hours, the same slot twice, who may accept, who
  may cancel, the database constraint itself, and that a cancelled visit cannot
  be accepted afterwards
- search: every filter, amenities combining with AND, ordering, a junk filter
  value, and that page one and page two never repeat a listing
- auth: weak passwords, duplicate email and NID, the six attempt lockout, the
  open redirect on `next`, deleting an account
- agent: approving, rejecting without a reason, withdrawing an approval, the
  decision history surviving three changes, GET refusals
- the dashboard and the saved searches pages

---

## Known limitations

- Tests cover the server side only; there are none for the JavaScript.
- No rate limiting on registration, only on sign in.
- Email is console-only unless SMTP settings are supplied.
- Images are resized on upload but not served in multiple sizes.
