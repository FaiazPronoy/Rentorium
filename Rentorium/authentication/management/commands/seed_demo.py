"""
Fills an empty database with believable demo data.

    python manage.py seed_demo

Everything it makes is deterministic, so the screenshots and the browser checks run
look the same every time. Use --wipe to start from scratch.
"""
import random
from authentication.demo import AGENT_PASSWORD, DEMO_PASSWORD
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from Agents.models import AgentAction
from authentication.models import Notification, UserProfile
from basic.models import Contact, Faq, Reviews
from property.models import (
    AllProperty, Amenity, Booking, CommercialProperty, Conversation, Favourite,
    LandProperty, Message, PropertyImage, PropertyReport, PropertyReview,
    PropertyView, RecentSearch, ResidentialProperty,
)

# The icon column is legacy; the site now draws an SVG chosen from the name
# (see basic/templatetags/icons.py), so these stay blank.
AMENITIES = [
    ('Lift', '', 'Building'), ('Generator', '', 'Building'),
    ('Parking', '', 'Building'), ('Security guard', '', 'Building'),
    ('CCTV', '', 'Building'), ('Rooftop access', '', 'Building'),
    ('Air conditioning', '', 'Inside'), ('Gas line', '', 'Inside'),
    ('Water reserve', '', 'Inside'), ('Balcony', '', 'Inside'),
    ('Gym', '', 'Extras'), ('Swimming pool', '', 'Extras'),
    ('Prayer room', '', 'Extras'), ('Community hall', '', 'Extras'),
    ('Internet ready', '', 'Extras'), ('Pet friendly', '', 'Extras'),
]

FAQS = [
    ('How long does approval take?',
     'Usually less than a day. One of our agents reads every new listing, and you get a '
     'notification the moment it goes live, or the moment it needs a small fix.'),
    ('Does it cost anything to list a property?',
     'No. Listing, messaging and booking viewings are all free, for owners and for '
     'people looking.'),
    ('Who can see my ownership papers?',
     'Only you and a verified agent. They are never shown on the public listing page, '
     'and the URL is checked on every request, not just hidden from the page.'),
    ('Can two people book the same viewing slot?',
     'No. Once the owner accepts a slot, the database itself refuses a second accepted '
     'booking at the same time for the same property.'),
    ('How do I get the verified badge?',
     'Upload the ownership paper with a listing. When an agent checks it, the badge is '
     'added to your profile and shows on all of your listings.'),
    ('Can I edit a listing after it goes live?',
     'Yes. An edit sends it back to the approval queue so an agent can look at what '
     'changed, then it goes live again.'),
    ('What happens when I delete my account?',
     'Everything goes with it: listings, photos, messages, bookings and reviews. '
     'It cannot be undone.'),
    ('Can I review a place I have not visited?',
     'You can, but please do not. Reviews are one per person per property, and you '
     'cannot review your own listing.'),
]

PEOPLE = [
    ('Faiaz Abrar', 'faiaz@rentorium.test', 'owner', '01711111111', True),
    ('Nabila Rahman', 'nabila@rentorium.test', 'owner', '01822222222', True),
    ('Rafid Hasan', 'rafid@rentorium.test', 'renter', '01911111111', False),
    ('Tasnim Jahan', 'tasnim@rentorium.test', 'renter', '01611111111', False),
    ('Arif Chowdhury', 'arif@rentorium.test', 'owner', '01511111111', False),
    ('Sadia Islam', 'sadia@rentorium.test', 'renter', '01311111111', False),
]

RESIDENTIAL = [
    ('Bright 3 bedroom flat near Gulshan 2 circle', 'Gulshan', 'Dhaka', 'rent', 78000, 1650,
     3, 3, 2, 'full', 'Beside Gulshan Society Mosque',
     'A corner flat on the seventh floor, with windows on two sides, so the sun '
     'finds you in the morning and the breeze finds you in the evening. It comes '
     'furnished down to the curtains. Two lifts, a standby generator, a guard on '
     'the gate, and Gulshan 2 circle is a ten minute walk.'),
    ('Quiet 2 bedroom in Dhanmondi, lake side', 'Dhanmondi', 'Dhaka', 'rent', 42000, 1100,
     2, 2, 1, 'semi', 'Two roads from Dhanmondi Lake',
     'A small, well kept building on a residential road, far enough from Satmasjid '
     'Road that you hear birds instead of horns. The living room looks out towards '
     'the lake. Right for a small family, or two friends who want their own rooms.'),
    ('Family duplex in Bashundhara block C', 'Bashundhara R/A', 'Dhaka', 'sale', 21500000, 2800,
     4, 4, 3, 'unfurnished', 'Near Apollo Hospital',
     'Two floors, the fifth and the sixth, joined by a staircase of their own. Four '
     'bedrooms, a separate drawing room for guests and a servant quarter. The '
     'kitchen was fitted last year and has never been cooked in.'),
    ('Furnished studio off Banani road 11', 'Banani', 'Dhaka', 'rent', 28000, 520,
     1, 1, 1, 'full', 'Off Banani road 11',
     'Everything you need and nothing you do not: bed, wardrobe, desk, fridge and '
     'an air conditioner, all included. The building is new and the road is '
     'quiet. Made for one person who works nearby and wants to walk to the office.'),
    ('Spacious 3 bedroom in Uttara sector 7', 'Uttara', 'Dhaka', 'rent', 35000, 1400,
     3, 2, 2, 'semi', 'Near Rajlakshmi complex',
     'South facing on the third floor, with a long balcony that runs past two '
     'rooms. Lift, generator and covered parking. The metro station is close '
     'enough that the drive to Motijheel stops being a daily argument.'),
    ('Two bedroom flat inside Mirpur DOHS', 'Mirpur', 'Dhaka', 'rent', 32000, 1150,
     2, 2, 1, 'unfurnished', 'Inside Mirpur DOHS',
     'A calm, gated neighbourhood with a park two minutes away, where children '
     'still play cricket in the evening. Fourth floor with a lift, and a water '
     'reserve tank so the dry months are not a worry.'),
]

COMMERCIAL = [
    ('Office floor in Mohakhali, 2400 sq ft', 'Mohakhali', 'Dhaka', 'rent', 145000, 2400,
     'office', 'Beside Rawa convention hall',
     'An open, light filled floor with a glass meeting room already built. Plug in '
     'and start on Monday. Two lifts, a generator for the whole building and '
     'parking for six cars.'),
    ('Ground floor shop on Dhanmondi road 27', 'Dhanmondi', 'Dhaka', 'rent', 95000, 800,
     'shop', 'On road 27, facing the main road',
     'Wide glass frontage on one of the busiest shopping roads in the city, so '
     'the shop sells itself to everyone walking past. Suits a boutique, a café '
     'or a clinic.'),
    ('Warehouse space in Badda', 'Badda', 'Dhaka', 'rent', 60000, 3200,
     'warehouse', 'Off Progoti Sharani',
     'One clear span with a roller shutter wide enough for a covered van, and a '
     'small office at the front for the paperwork. Trucks can come straight in '
     'from the main road.'),
]

LAND = [
    ('5 katha plot in Bashundhara block J', 'Bashundhara R/A', 'Dhaka', 'sale', 32000000, 3600,
     'residential_plot', 'Two roads from the main gate',
     'A corner plot on a 40 foot road, ready to build on, with the boundary wall '
     'already up. The papers are clean and in one name, which in this city is '
     'rarer than it should be.'),
    ('Commercial plot facing Motijheel main road', 'Motijheel', 'Dhaka', 'sale', 78000000, 5200,
     'commercial_plot', 'Near Dilkusha',
     'Main road frontage in the old business district, the kind of plot that '
     'almost never comes up. Suits an office tower. Sold with the survey and '
     'mutation papers.'),
]

# which photographs go with which listing, from static/img/photos
PHOTOS = {
    'residential': [
        ['gulshan-1', 'gulshan-2', 'gulshan-3', 'gulshan-4'],
        ['dhanmondi-1', 'dhanmondi-2', 'dhanmondi-3', 'dhanmondi-4'],
        ['duplex-1', 'extra-4', 'duplex-3', 'duplex-4'],
        ['studio-1', 'studio-2', 'studio-3', 'studio-4'],
        ['uttara-1', 'uttara-2', 'uttara-3', 'uttara-4'],
        ['mirpur-1', 'mirpur-2', 'mirpur-3', 'mirpur-4'],
    ],
    'commercial': [
        ['office-1', 'office-2', 'office-3', 'office-4'],
        ['shop-1', 'shop-2', 'shop-3'],
        ['warehouse-1', 'warehouse-2'],
    ],
    'land': [
        ['plot-1', 'plot-2', 'plot-3'],
        ['cityplot-1', 'cityplot-2', 'cityplot-3'],
    ],
    'pending': ['extra-1', 'extra-2', 'extra-3'],
}

REVIEWS = [
    (5, 'Exactly like the photos', 'The pictures were honest, the owner came on time for '
     'the viewing, and the flat was cleaner than we expected. We moved in a week later.'),
    (4, 'Lovely flat, slow lift', 'Really happy with the flat itself. The lift crawls a '
     'bit around office hours, and that is honestly the only complaint.'),
    (5, 'No surprises', 'No hidden service charge and no last minute change to the '
     'advance. What the listing said is exactly what we signed.'),
    (4, 'Bright and quiet', 'The road is calmer than I expected for the area, and the '
     'morning light in the bedroom is the best part of my day.'),
    (3, 'Nice place, ask about water', 'Good value for the rent. Water pressure on the top '
     'floors drops in the evening though, so ask the owner about it.'),
]

SITE_REVIEWS = [
    (5, 'Found our flat in four days. Knowing a real person had checked every listing '
        'meant we stopped wasting Fridays on places that did not exist.'),
    (5, 'I booked a viewing without making five phone calls. The owner confirmed the '
        'time within an hour, which honestly shocked me.'),
    (5, 'The map made it easy. I could see which flats were near my office before I '
        'even opened them.'),
    (5, 'I rent out two flats here. The dashboard shows how many people looked and how '
        'many saved them, and no other site bothers to tell you that.'),
    (4, 'Quick and simple. Photos being required means you know what you are walking '
        'into before you go.'),
]


class Command(BaseCommand):
    help = 'Fills the database with demo data for screenshots and trying it out.'

    def add_arguments(self, parser):
        parser.add_argument('--wipe', action='store_true',
                            help='Delete existing demo data first.')

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(471)
        now = timezone.now()

        if options['wipe']:
            self.stdout.write('Wiping…')
            AllProperty.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            Reviews.objects.all().delete()
            Contact.objects.all().delete()
            Faq.objects.all().delete()

        # ---------------------------------------------------- amenities --
        amenities = {}
        for name, icon, group in AMENITIES:
            amenity, _ = Amenity.objects.get_or_create(
                name=name, defaults={'icon': icon, 'group': group})
            amenities[name] = amenity
        self.stdout.write(f'  {len(amenities)} amenities')

        # --------------------------------------------------------- FAQs --
        for i, (question, answer) in enumerate(FAQS):
            Faq.objects.get_or_create(question=question,
                                      defaults={'answer': answer, 'position': i})
        self.stdout.write(f'  {len(FAQS)} FAQs')

        # -------------------------------------------------------- users --
        colours = ['#1D4E9E', '#A4552F', '#0B2545', '#6E5A7D', '#7A5A00', '#0E6E86']
        profiles = {}

        agent_user, created = User.objects.get_or_create(
            username='agent@rentorium.test',
            defaults={'email': 'agent@rentorium.test'})
        if created:
            agent_user.set_password(AGENT_PASSWORD)
            agent_user.save()
        agent = agent_user.UserProfile
        agent.name = 'Tahmid Karim'
        agent.email = 'agent@rentorium.test'
        agent.role = UserProfile.Role.AGENT
        agent.is_agent = True
        agent.is_verified = True
        agent.contact_no = '01700000000'
        agent.avatar_color = '#0B2545'
        agent.bio = 'Agent at Rentorium. I check every listing before it goes live.'
        agent.save()
        profiles['agent'] = agent

        for i, (name, email, role, phone, verified) in enumerate(PEOPLE):
            user, created = User.objects.get_or_create(
                username=email, defaults={'email': email})
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            profile = user.UserProfile
            profile.name = name
            profile.email = email
            profile.role = role
            profile.contact_no = phone
            profile.is_verified = verified
            profile.avatar_color = colours[i % len(colours)]
            profile.nid = f'19900{i}1234567'
            profile.bio = (
                'I let out flats in Dhaka and answer messages quickly.'
                if role == 'owner' else
                'Looking for a place near work, ready to move soon.'
            )
            profile.created_at = now - timedelta(days=150 - i * 20)
            profile.save()
            profiles[email] = profile

        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@rentorium.test', 'Admin@2026')
        self.stdout.write(f'  {len(profiles)} profiles plus a superuser')

        # ---------------------------------------------------- listings --
        owners = [profiles[e] for _, e, r, _, _ in PEOPLE if r == 'owner']
        photo_dir = Path(settings.BASE_DIR) / 'static' / 'img' / 'photos'
        listings = []

        # Any file already sitting in media/pics makes Django rename the next
        # upload with a random suffix, so a re-seed used to leave the database
        # pointing at names that only exist on the machine that ran it. Clear
        # the folder first and every seed produces the same filenames.
        pics_dir = Path(settings.MEDIA_ROOT) / 'pics'
        if pics_dir.exists():
            for old in pics_dir.glob('*'):
                if old.is_file():
                    try:
                        old.unlink()
                    except OSError:
                        pass

        def attach_images(listing, names):
            for n, name in enumerate(names):
                path = photo_dir / f'{name}.jpg'
                if not path.exists():
                    continue
                with path.open('rb') as fh:
                    PropertyImage.objects.create(
                        property=listing,
                        image=File(fh, name=f'{listing.pk}-{n}-{path.name}'),
                        position=n,
                    )

        # A short stand-in for the ownership paper. It lives outside
        # MEDIA_ROOT like a real one, so the demo exercises the checked
        # document view rather than a public /media/ URL.
        docs_dir = Path(settings.PRIVATE_MEDIA_ROOT) / 'property_documents'
        if docs_dir.exists():
            for old in docs_dir.glob('*'):
                if old.is_file():
                    try:
                        old.unlink()
                    except OSError:
                        pass

        def attach_document(listing):
            """A one page PDF that says what it is, written by hand.

            Building it here rather than shipping a binary keeps the repository
            text only, and gives the demo something that actually renders in
            the viewer on the papers page.
            """
            lines = [
                ('DEED OF OWNERSHIP', 24, 700),
                ('SAMPLE DOCUMENT - DEMONSTRATION DATA ONLY', 11, 668),
                ('Property: ' + listing.Property_Name[:56], 12, 620),
                ('Address: ' + listing.full_address[:56], 12, 596),
                ('Holder: ' + listing.user.name, 12, 572),
                ('Mutation and survey papers verified.', 12, 548),
            ]

            def esc(s):
                for a, b in (('\\', ''), ('(', ''), (')', '')):
                    s = s.replace(a, b)
                return s.encode('ascii', 'replace').decode('ascii')

            text = 'BT\n' + ''.join(
                '/F1 %d Tf 1 0 0 1 60 %d Tm (%s) Tj\n' % (size, y, esc(t))
                for t, size, y in lines) + 'ET\n'
            stream = text.encode()
            objs = [
                b'<</Type/Catalog/Pages 2 0 R>>',
                b'<</Type/Pages/Kids[3 0 R]/Count 1>>',
                b'<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]'
                b'/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>',
                b'<</Length %d>>\nstream\n%s\nendstream' % (len(stream), stream),
                b'<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>',
            ]
            out = bytearray(b'%PDF-1.4\n')
            offsets = []
            for i, body in enumerate(objs, start=1):
                offsets.append(len(out))
                out += b'%d 0 obj\n' % i + body + b'\nendobj\n'
            start = len(out)
            out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
            for off in offsets:
                out += b'%010d 00000 n \n' % off
            out += (b'trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n'
                    % (len(objs) + 1, start))
            listing.Property_Documents.save(
                f'{listing.pk}-ownership.pdf', ContentFile(bytes(out)), save=True)

        def finish(listing, i, extras, photos):
            listing.status = AllProperty.Status.APPROVED
            listing.needs_approval = False
            listing.Approval_by_Agent = agent.name
            listing.approved_at = now - timedelta(days=30 - i)
            listing.created_at = now - timedelta(days=32 - i)
            listing.is_featured = i < 3
            listing.view_count = random.randint(24, 380)
            listing.save()
            listing.amenities.set([amenities[a] for a in extras if a in amenities])
            attach_images(listing, photos)
            attach_document(listing)
            AgentAction.objects.create(
                agent=agent, property=listing,
                action=AgentAction.Action.APPROVED,
                reason='Details and photos check out.',
            )
            listings.append(listing)

        pools = [
            ['Lift', 'Generator', 'Parking', 'Security guard', 'Air conditioning', 'Gas line'],
            ['Lift', 'Water reserve', 'Balcony', 'Internet ready'],
            ['Parking', 'Rooftop access', 'CCTV', 'Community hall', 'Prayer room'],
            ['Lift', 'Air conditioning', 'Internet ready', 'Pet friendly'],
            ['Lift', 'Generator', 'Parking', 'Balcony', 'Water reserve'],
            ['Lift', 'Water reserve', 'Gas line', 'Security guard'],
        ]

        for i, row in enumerate(RESIDENTIAL):
            (title, area, city, on, price, sqft, beds, baths, balc,
             furnishing, landmark, description) = row
            listing = ResidentialProperty(
                user=owners[i % len(owners)], Property_Name=title,
                Property_Description=description, Property_type='residential',
                Property_on=on, Price=price, Total_area_in_sqft=sqft,
                service_charge=3500 if on == 'rent' else 0,
                security_deposit_months=2 if on == 'rent' else 0,
                negotiable=(i % 3 == 0),
                City=city, Area=area, landmark=landmark,
                Road_No=str(10 + i), Block=chr(65 + i), Postal_code='121%d' % (i % 10),
                furnishing=furnishing, available_from=(now + timedelta(days=7 * i)).date(),
                House_No=f'{12 + i}', floor_number=(i % 6) + 2, Floor_count=8,
                Bedrooms=beds, Bathrooms=baths, Number_of_Balcony=balc,
                Garage_spaces_Per_Sqft=1 if i % 2 else 0,
                has_lift=True, Has_Pool=(i == 2), Has_Garden=(i == 2),
                Year=(now - timedelta(days=365 * (3 + i))).date(),
            )
            finish(listing, i, pools[i % len(pools)], PHOTOS['residential'][i])

        for j, row in enumerate(COMMERCIAL):
            (title, area, city, on, price, sqft, use, landmark, description) = row
            i = len(RESIDENTIAL) + j
            listing = CommercialProperty(
                user=owners[j % len(owners)], Property_Name=title,
                Property_Description=description, Property_type='commercial',
                Property_on=on, Price=price, Total_area_in_sqft=sqft,
                service_charge=8000, security_deposit_months=3,
                City=city, Area=area, landmark=landmark,
                Road_No=str(3 + j), Block='C', Postal_code='1212',
                furnishing='semi', available_from=(now + timedelta(days=14)).date(),
                House_No=f'{40 + j}', Business_type=use, Parking_spaces=4 + j,
                Has_elevator=True, Has_security_system=True,
                Has_conference_room=(use == 'office'), has_generator=True,
                Year=(now - timedelta(days=365 * 6)).date(),
            )
            finish(listing, i, ['Lift', 'Generator', 'Parking', 'CCTV', 'Security guard'],
                   PHOTOS['commercial'][j])

        for k, row in enumerate(LAND):
            (title, area, city, on, price, sqft, kind, landmark, description) = row
            i = len(RESIDENTIAL) + len(COMMERCIAL) + k
            listing = LandProperty(
                user=owners[k % len(owners)], Property_Name=title,
                Property_Description=description, Property_type='land',
                Property_on=on, Price=price, Total_area_in_sqft=sqft,
                City=city, Area=area, landmark=landmark,
                Road_No=str(5 + k), Block='J', Postal_code='1229',
                Land_type=kind, Road_size_in_sqft=40 - k * 10, Is_fenced=(k == 0),
                has_water_connection=True, has_gas_connection=(k == 0),
            )
            finish(listing, i, ['Water reserve', 'Gas line'], PHOTOS['land'][k])

        # one still waiting, so the agent queue is not empty
        pending = ResidentialProperty(
            user=owners[0],
            Property_Name='Newly finished 2 bedroom in Banani DOHS',
            Property_Description=(
                'Handed over last month and nobody has lived in it yet, so you would be '
                'the first. Two bedrooms, an open kitchen and a balcony that catches the '
                'afternoon sun.'
            ),
            Property_type='residential', Property_on='rent', Price=46000,
            Total_area_in_sqft=1180, service_charge=4000, security_deposit_months=2,
            City='Dhaka', Area='Banani', landmark='Inside Banani DOHS',
            Road_No='9', Block='D', Postal_code='1213', furnishing='unfurnished',
            available_from=(now + timedelta(days=20)).date(),
            House_No='7', floor_number=3, Floor_count=7, Bedrooms=2, Bathrooms=2,
            Number_of_Balcony=1, has_lift=True,
        )
        pending.status = AllProperty.Status.PENDING
        pending.created_at = now - timedelta(hours=6)
        pending.save()
        pending.amenities.set([amenities['Lift'], amenities['Generator']])
        attach_images(pending, PHOTOS['pending'])

        # one that was sent back, so the owner view shows that state too
        rejected = ResidentialProperty(
            user=owners[1],
            Property_Name='Sublet room available in Mirpur 10',
            Property_Description='One room in a shared flat.',
            Property_type='residential', Property_on='rent', Price=9000,
            Total_area_in_sqft=180, City='Dhaka', Area='Mirpur',
            Road_No='2', Postal_code='1216', House_No='4',
            floor_number=2, Floor_count=5, Bedrooms=1, Bathrooms=1,
        )
        rejected.status = AllProperty.Status.REJECTED
        rejected.rejection_reason = (
            'Please add at least two photos and the ownership or tenancy paper.'
        )
        rejected.Approval_by_Agent = 'Cancel'
        rejected.created_at = now - timedelta(days=3)
        rejected.save()
        AgentAction.objects.create(
            agent=agent, property=rejected, action=AgentAction.Action.REJECTED,
            reason=rejected.rejection_reason,
        )
        self.stdout.write(f'  {len(listings)} live listings, 1 waiting, 1 sent back')

        # ---------------------------------------------- the view history --
        # view_count on its own left every chart on the site flat: the owner
        # dashboard, the agent stats page and the per listing analytics all
        # read PropertyView rows, not the counter. Seed the real rows and let
        # the counter be their total, so the number and the graph agree.
        today = timezone.localdate()
        everyone = list(profiles.values())
        view_rows = []
        for listing in listings:
            total = 0
            for back in range(29, -1, -1):
                day = today - timedelta(days=back)
                # busier in the last fortnight, and quieter at the weekend
                base = 9 if back < 14 else 4
                if day.weekday() in (4, 5):
                    base = max(1, base - 3)
                for n in range(random.randint(0, base)):
                    view_rows.append(PropertyView(
                        property=listing,
                        profile=random.choice(everyone) if n % 3 == 0 else None,
                        session_key=f'seed{listing.pk}-{back}-{n}',
                        viewed_on=day,
                    ))
                    total += 1
            listing.view_count = total
        PropertyView.objects.bulk_create(view_rows, batch_size=500)
        AllProperty.objects.bulk_update(listings, ['view_count'])
        self.stdout.write(f'  {len(view_rows)} views over the last 30 days')

        # ------------------------------------------- reviews, saves, etc --
        renters = [profiles[e] for _, e, r, _, _ in PEOPLE if r == 'renter']
        for i, listing in enumerate(listings[:5]):
            for j, renter in enumerate(renters[:2]):
                rating, title, comment = REVIEWS[(i + j) % len(REVIEWS)]
                PropertyReview.objects.get_or_create(
                    property=listing, author=renter,
                    defaults={'rating': rating, 'title': title, 'comment': comment},
                )
            for renter in renters:
                if (i + len(renter.name)) % 2 == 0:
                    Favourite.objects.get_or_create(profile=renter, property=listing)

        for i, (rating, comment) in enumerate(SITE_REVIEWS):
            author = list(profiles.values())[i % len(profiles)]
            Reviews.objects.get_or_create(
                user=author, defaults={'rating': rating, 'comment': comment})

        # ------------------------------------------------------ bookings --
        slots = [(1, 11), (2, 16), (3, 10), (5, 17)]
        for i, (days, hour) in enumerate(slots):
            listing = listings[i % len(listings)]
            renter = renters[i % len(renters)]
            if renter == listing.user:
                continue
            Booking.objects.get_or_create(
                property=listing, renter=renter,
                visit_date=(now + timedelta(days=days)).date(),
                visit_time=timezone.datetime.min.time().replace(hour=hour),
                defaults={
                    'owner': listing.user,
                    'message': 'Would this time work? I can come any day this week.',
                    'status': [Booking.Status.PENDING, Booking.Status.ACCEPTED,
                               Booking.Status.PENDING, Booking.Status.DECLINED][i],
                    'owner_response': 'Sorry, I am out of town that day.' if i == 3 else '',
                },
            )

        # ----------------------------------------------------- messaging --
        for i in range(3):
            listing = listings[i]
            renter = renters[i % len(renters)]
            if renter == listing.user:
                continue
            thread, _ = Conversation.objects.get_or_create(
                property=listing, renter=renter, defaults={'owner': listing.user})
            if not thread.messages.exists():
                Message.objects.create(
                    conversation=thread, sender=renter,
                    body='Hello, is this still available? And is the service charge '
                         'included in the rent you listed?')
                Message.objects.create(
                    conversation=thread, sender=listing.user, is_read=True,
                    body='Yes, still available. The service charge is separate, it is '
                         'listed under the price. Happy to show you this weekend.')
            thread.last_message_at = now - timedelta(hours=3 * i + 1)
            thread.save(update_fields=['last_message_at'])

        # ----------------------------------------------------- enquiries --
        Contact.objects.get_or_create(
            subject='Listing stuck in review',
            defaults={
                'name': 'Imran Kabir', 'email': 'imran@example.com',
                'message': 'I put up a flat in Uttara two days ago and it still says '
                           'waiting for approval. Is something missing from it?',
            },
        )
        Contact.objects.get_or_create(
            subject='Can I list from outside Dhaka?',
            defaults={
                'name': 'Shirin Akter', 'email': 'shirin@example.com',
                'message': 'I have a house in Sylhet. Does the site cover areas outside '
                           'Dhaka yet?',
                'status': Contact.Status.ANSWERED,
                'reply': 'Yes, Sylhet, Chattogram, Khulna and Rajshahi are all covered.',
            },
        )

        # ------------------------------------------------ recent searches --
        # So the suggestion box under the search field has something to show
        # the moment a demo account signs in.
        searchers = [profiles['rafid@rentorium.test'],
                     profiles['tasnim@rentorium.test']]
        history = [
            ('gulshan', 'q=gulshan'),
            ('3 bedroom', 'q=3+bedroom&property_type=residential'),
            ('office mohakhali', 'q=office+mohakhali&property_type=commercial'),
            ('dhanmondi lake', 'q=dhanmondi+lake'),
            ('katha', 'q=katha&property_type=land'),
        ]
        for who in searchers:
            for n, (term, qs) in enumerate(history):
                row = RecentSearch.remember(
                    who, term, qs,
                    AllProperty.objects.live().filter(
                        Q(Property_Name__icontains=term.split()[0])
                        | Q(Area__icontains=term.split()[0])).count(),
                )
                if row:
                    RecentSearch.objects.filter(pk=row.pk).update(
                        searched_at=now - timedelta(hours=3 + n * 14))

        # ------------------------------------------------------- reports --
        # One open report for the agent queue, one already dealt with, so the
        # page shows both halves of the workflow.
        live_rows = list(AllProperty.objects.live().order_by('pk'))
        if len(live_rows) >= 2:
            open_report = PropertyReport.objects.create(
                property=live_rows[1],
                reporter=profiles['rafid@rentorium.test'],
                reason=PropertyReport.Reason.TAKEN,
                detail='I called the number on Tuesday and the owner said it was '
                       'let two weeks ago. It is still showing as available.',
            )
            PropertyReport.objects.filter(pk=open_report.pk).update(
                created_at=now - timedelta(days=1, hours=4))

            closed = PropertyReport.objects.create(
                property=live_rows[0],
                reporter=profiles['tasnim@rentorium.test'],
                reason=PropertyReport.Reason.WRONG,
                detail='The floor plan in the third photo does not look like the '
                       'same flat as the first two.',
                status=PropertyReport.Status.DISMISSED,
                handled_by=agent,
                handled_at=now - timedelta(days=4),
                outcome='Checked with the owner: all three photos are the same '
                        'flat, taken before and after painting.',
            )
            PropertyReport.objects.filter(pk=closed.pk).update(
                created_at=now - timedelta(days=5))
            AgentAction.objects.create(
                agent=agent, property=live_rows[0],
                action=AgentAction.Action.REPORT_DISMISSED,
                reason='Photos check out against the owner’s own copies.',
            )

        # -------------------------------------------------- notifications --
        for profile in profiles.values():
            Notification.push(
                profile, f'Welcome to {settings.SITE_NAME}',
                'Your account is ready. Finish your profile so owners know who '
                'they are speaking to.',
                '/account/edit-profile', Notification.Kind.SYSTEM,
            )

        # ------------------------------------------------- realistic dates --
        # created_at on reviews, decisions and enquiries is auto_now_add, so
        # without this every one of them is stamped with the moment the seed
        # ran. A page of reviews all written today reads as fake.
        for n, pk in enumerate(PropertyReview.objects.order_by('pk')
                               .values_list('pk', flat=True)):
            PropertyReview.objects.filter(pk=pk).update(
                created_at=now - timedelta(days=5 + n * 11, hours=(n * 7) % 24),
                updated_at=now - timedelta(days=5 + n * 11),
            )
        for n, pk in enumerate(Reviews.objects.order_by('pk')
                               .values_list('pk', flat=True)):
            Reviews.objects.filter(pk=pk).update(
                date=now - timedelta(days=9 + n * 19, hours=(n * 5) % 24))
        for n, pk in enumerate(AgentAction.objects.order_by('pk')
                               .values_list('pk', flat=True)):
            AgentAction.objects.filter(pk=pk).update(
                created_at=now - timedelta(days=n, hours=(n * 3) % 20 + 1))
        for n, pk in enumerate(Contact.objects.order_by('pk')
                               .values_list('pk', flat=True)):
            Contact.objects.filter(pk=pk).update(
                created_at=now - timedelta(days=2 + n * 4))
        for n, pk in enumerate(Message.objects.order_by('pk')
                               .values_list('pk', flat=True)):
            Message.objects.filter(pk=pk).update(
                created_at=now - timedelta(hours=6 + n * 5))
        for n, pk in enumerate(Notification.objects.order_by('pk')
                               .values_list('pk', flat=True)):
            Notification.objects.filter(pk=pk).update(
                created_at=now - timedelta(hours=1 + n * 9))

        self.stdout.write(self.style.SUCCESS('\nDemo data ready.\n'))
        self.stdout.write('  Agent      agent@rentorium.test / Agent@2026')
        self.stdout.write('  Owner      faiaz@rentorium.test / Rentorium@2026')
        self.stdout.write('  Renter     rafid@rentorium.test / Rentorium@2026')
        self.stdout.write('  Superuser  admin / Admin@2026')
