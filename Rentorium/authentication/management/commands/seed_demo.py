"""
Fills an empty database with believable demo data.

    python manage.py seed_demo

Everything it makes is deterministic, so the screenshots and the marking run
look the same every time. Use --wipe to start from scratch.
"""
import random
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
     'An agent usually reviews a new listing within a day. You get a notification the '
     'moment it goes live, or the moment it comes back with something to fix.'),
    ('Does it cost anything to list a property?',
     'No. Listing, messaging and bookings are all free.'),
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
     'A corner flat on the seventh floor with windows on two sides, so it stays bright '
     'all day and cool in the evening. Two lifts, a standby generator and a guard on '
     'the gate. Ten minutes on foot to Gulshan 2 circle.'),
    ('Quiet 2 bedroom in Dhanmondi, lake side', 'Dhanmondi', 'Dhaka', 'rent', 42000, 1100,
     2, 2, 1, 'semi', 'Two roads from Dhanmondi Lake',
     'A small, well kept building on a residential road, away from the traffic. The '
     'living room looks out over the lake road. Good for a small family or two '
     'people sharing.'),
    ('Family duplex in Bashundhara block C', 'Bashundhara R/A', 'Dhaka', 'sale', 21500000, 2800,
     4, 4, 3, 'unfurnished', 'Near Apollo Hospital',
     'A duplex across the fifth and sixth floors, with its own stair between them. '
     'Four bedrooms, a separate drawing room and a servant quarter. Fitted kitchen, '
     'never used.'),
    ('Studio near Banani 11, furnished', 'Banani', 'Dhaka', 'rent', 28000, 520,
     1, 1, 1, 'full', 'Off Banani road 11',
     'A furnished studio in a newer building. Bed, wardrobe, desk, fridge and an air '
     'conditioner are all included. Suits one person working nearby.'),
    ('Spacious 3 bed in Uttara sector 7', 'Uttara', 'Dhaka', 'rent', 35000, 1400,
     3, 2, 2, 'semi', 'Near Rajlakshmi complex',
     'Third floor, south facing, with a long balcony that runs across two rooms. '
     'The building has a lift, a generator and covered parking.'),
    ('Two bedroom in Mirpur DOHS', 'Mirpur', 'Dhaka', 'rent', 32000, 1150,
     2, 2, 1, 'unfurnished', 'Inside Mirpur DOHS',
     'A calm, secure neighbourhood with a park two minutes away. The flat is on the '
     'fourth floor with a lift, and there is a water reserve tank for the dry months.'),
]

COMMERCIAL = [
    ('Office floor in Mohakhali, 2400 sq ft', 'Mohakhali', 'Dhaka', 'rent', 145000, 2400,
     'office', 'Beside Rawa convention hall',
     'An open floor with a small partitioned meeting room, ready to move into. Two '
     'lifts, a full building generator and parking for six cars.'),
    ('Ground floor shop on Dhanmondi road 27', 'Dhanmondi', 'Dhaka', 'rent', 95000, 800,
     'shop', 'On road 27, main road facing',
     'Main road frontage with a wide glass front, on one of the busiest retail roads '
     'in the city. Suits a showroom, a café or a clinic.'),
    ('Warehouse space in Badda', 'Badda', 'Dhaka', 'rent', 60000, 3200,
     'warehouse', 'Off Progoti Sharani',
     'A single span shed with a roller shutter wide enough for a covered van, and a '
     'small office at the front. Truck access from the main road.'),
]

LAND = [
    ('5 katha plot in Bashundhara block J', 'Bashundhara R/A', 'Dhaka', 'sale', 32000000, 3600,
     'residential_plot', 'Two roads from the main gate',
     'A ready to build corner plot on a 40 foot road, with the boundary wall already '
     'up. All the paperwork is clean and in one name.'),
    ('Commercial plot facing Motijheel main road', 'Motijheel', 'Dhaka', 'sale', 78000000, 5200,
     'commercial_plot', 'Near Dilkusha',
     'A rare main road plot in the old commercial district, suitable for an office '
     'building. Sold with the survey and mutation papers.'),
]

REVIEWS = [
    (5, 'Exactly as described', 'The photos were honest, the owner turned up on time for '
     'the viewing, and the flat was cleaner than I expected. Moved in a week later.'),
    (4, 'Good place, small lift', 'Really happy with the flat itself. The building lift is '
     'a bit slow at peak hours, which is the only thing I would mention.'),
    (5, 'Owner was straight with us', 'No hidden service charge, no last minute change to '
     'the deposit. Everything was what the listing said it was.'),
    (4, 'Bright and quiet', 'The road is calmer than I thought it would be for that area. '
     'Good natural light in the mornings.'),
    (3, 'Fine, but the water pressure', 'The place is decent for the price. Water pressure '
     'on the upper floors drops in the evening, worth asking about.'),
]

SITE_REVIEWS = [
    (5, 'I found a flat in four days. Being able to see which listings an agent had '
        'actually checked made the difference.'),
    (5, 'Booking a viewing without five phone calls is the whole reason I used this. '
        'The owner confirmed the slot in an hour.'),
    (4, 'Good filters. I would like a map view, but the area filter got me close enough.'),
    (5, 'I list two flats here. The dashboard tells me how many people looked and how '
        'many saved it, which no other site bothers to show.'),
    (4, 'Straightforward and quick. The photos being required really helps.'),
]


class Command(BaseCommand):
    help = 'Fills the database with demo data for screenshots and marking.'

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
        colours = ['#46552F', '#A4552F', '#232719', '#6E5A7D', '#B07A2A', '#4C6B7A']
        profiles = {}

        agent_user, created = User.objects.get_or_create(
            username='agent@rentorium.test',
            defaults={'email': 'agent@rentorium.test'})
        if created:
            agent_user.set_password('Agent@2026')
            agent_user.save()
        agent = agent_user.UserProfile
        agent.name = 'Reshad Karim'
        agent.email = 'agent@rentorium.test'
        agent.role = UserProfile.Role.AGENT
        agent.is_agent = True
        agent.is_verified = True
        agent.contact_no = '01700000000'
        agent.avatar_color = '#232719'
        agent.bio = 'Agent at Rentorium. I check every listing before it goes live.'
        agent.save()
        profiles['agent'] = agent

        for i, (name, email, role, phone, verified) in enumerate(PEOPLE):
            user, created = User.objects.get_or_create(
                username=email, defaults={'email': email})
            if created:
                user.set_password('Rentorium@2026')
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
        img_dir = Path(settings.BASE_DIR) / 'static' / 'img'
        stock = sorted(img_dir.glob('property-*.jpg'))
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

        def attach_images(listing, start):
            if not stock:
                return
            for n in range(3):
                path = stock[(start + n) % len(stock)]
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

        def finish(listing, i, extras):
            listing.status = AllProperty.Status.APPROVED
            listing.needs_approval = False
            listing.Approval_by_Agent = agent.name
            listing.approved_at = now - timedelta(days=30 - i)
            listing.created_at = now - timedelta(days=32 - i)
            listing.is_featured = i < 3
            listing.view_count = random.randint(24, 380)
            listing.save()
            listing.amenities.set([amenities[a] for a in extras if a in amenities])
            attach_images(listing, i)
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
            finish(listing, i, pools[i % len(pools)])

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
            finish(listing, i, ['Lift', 'Generator', 'Parking', 'CCTV', 'Security guard'])

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
            finish(listing, i, ['Water reserve', 'Gas line'])

        # one still waiting, so the agent queue is not empty
        pending = ResidentialProperty(
            user=owners[0],
            Property_Name='Newly finished 2 bedroom in Banani DOHS',
            Property_Description=(
                'Handed over last month, nobody has lived in it yet. Two bedrooms, an '
                'open kitchen and a balcony that catches the afternoon sun.'
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
        attach_images(pending, 2)

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
