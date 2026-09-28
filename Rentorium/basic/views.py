from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Avg, Count
from django.shortcuts import redirect, render

from authentication.decorators import login_required_message, post_required, profile_of
from property.models import AllProperty

from .forms import ContactForm, ReviewForm
from .models import Faq, Reviews


# home

def home(request):
    live = AllProperty.objects.live()

    # The home page lays these out as one large card and four small ones, so
    # it wants exactly five. Take the featured listings first and top the row
    # up with the newest ones rather than leaving holes in the grid.
    WANTED = 5
    featured = list(live.filter(is_featured=True).with_cards()
                    .order_by('-approved_at', '-created_at')[:WANTED])
    if len(featured) < WANTED:
        seen = [p.pk for p in featured]
        featured += list(live.exclude(pk__in=seen).with_cards()
                         .order_by('-created_at')[:WANTED - len(featured)])

    context = {
        'featured': featured,
        'newest': live.with_cards().order_by('-created_at')[:6],
        # The carousel shows three at a time, so give it enough to turn.
        'top_review': Reviews.objects.filter(is_published=True)
                                     .select_related('user')[:9],
        'counts': {
            'total': live.count(),
            'rent': live.filter(Property_on='rent').count(),
            'sale': live.filter(Property_on='sale').count(),
            'residential': live.filter(Property_type='residential').count(),
            'commercial': live.filter(Property_type='commercial').count(),
            'land': live.filter(Property_type='land').count(),
            'areas': live.values('Area').distinct().count(),
        },
        'areas': (live.values('Area')
                      .annotate(n=Count('id'))
                      .order_by('-n')[:10]),
        'active': 'home',
    }
    return render(request, 'index.html', context)


# flat pages

def about(request):
    live = AllProperty.objects.live()
    return render(request, 'about.html', {
        'active': 'about',
        'stats': {
            'listings': live.count(),
            'areas': live.values('Area').distinct().count(),
            'owners': live.values('user').distinct().count(),
            'reviews': Reviews.objects.filter(is_published=True).count(),
        },
    })


def faqs(request):
    rows = Faq.objects.filter(is_published=True)
    return render(request, 'faqs.html', {'faqs': rows, 'active': 'faqs'})


def license(request):
    return render(request, 'license.html', {'active': 'license'})


def terms(request):
    return render(request, 'terms.html', {'active': 'terms'})


def notFound(request):
    return render(request, '404.html', status=404)


def handler404(request, exception=None):
    return render(request, '404.html', status=404)


def handler500(request):
    return render(request, '500.html', status=500)


# testimonial

def testimonial(request):
    me = profile_of(request)
    mine = Reviews.objects.filter(user=me).first() if me else None

    if request.method == 'POST':
        if me is None:
            messages.info(request, 'Please sign in to leave a review.')
            return redirect(f"{request.path}")
        form = ReviewForm(request.POST, instance=mine)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = me
            review.save()
            messages.success(
                request,
                'Your review has been updated.' if mine else 'Thanks for the review.'
            )
            return redirect('testimonial')
        messages.error(request, 'Please check the form and try again.')
    else:
        form = ReviewForm(instance=mine)

    published = (Reviews.objects.filter(is_published=True)
                 .select_related('user').order_by('-rating', '-date'))
    summary = published.aggregate(avg=Avg('rating'), n=Count('id'))

    breakdown = []
    total = summary['n'] or 0
    for star in range(5, 0, -1):
        count = published.filter(rating=star).count()
        breakdown.append({
            'star': star,
            'count': count,
            'pct': round(count / total * 100) if total else 0,
        })

    paginator = Paginator(published, 8)
    try:
        page = paginator.page(request.GET.get('page'))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    return render(request, 'testimonial.html', {
        'all_review': page,
        'form': form,
        'mine': mine,
        'average': round(summary['avg'], 1) if summary['avg'] else None,
        'review_count': total,
        'breakdown': breakdown,
        'active': 'testimonial',
    })


@login_required_message
@post_required
def delete_testimonial(request):
    Reviews.objects.filter(user=profile_of(request)).delete()
    messages.success(request, 'Your review has been removed.')
    return redirect('testimonial')


# contact

def contact(request):
    me = profile_of(request)
    initial = {}
    if me:
        initial = {'name': me.name, 'email': me.email}

    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            enquiry = form.save()
            _send_contact_mail(enquiry)
            messages.success(
                request, 'Thanks, your message is with us. We will reply by email.'
            )
            return redirect('contact')
        messages.error(request, 'Please check the form and try again.')
    else:
        form = ContactForm(initial=initial)

    return render(request, 'contact.html', {'form': form, 'active': 'contact'})


def _send_contact_mail(enquiry):
    """Never let a mail failure lose the message: it is already in the database."""
    support = settings.SUPPORT_EMAIL or settings.DEFAULT_FROM_EMAIL
    body = (
        f'From: {enquiry.name} <{enquiry.email}>\n'
        f'Subject: {enquiry.subject}\n\n{enquiry.message}'
    )
    try:
        send_mail(f'[Rentorium] {enquiry.subject}', body,
                  settings.DEFAULT_FROM_EMAIL, [support], fail_silently=True)
        send_mail(
            'We have your message',
            f'Hello {enquiry.name},\n\nThanks for writing in. '
            'Someone will reply to this address soon.\n\n- The Rentorium team',
            settings.DEFAULT_FROM_EMAIL, [enquiry.email], fail_silently=True,
        )
    except Exception:
        pass
