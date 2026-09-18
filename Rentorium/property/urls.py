"""
URLs for everything to do with a property.

Written as words a person could read out. The listing route carries the slug
after the id, so a link that gets pasted into a message still says what it
points at; the id-only form keeps working, which is what internal `reverse`
calls with a single argument produce.

Order matters below: `listing/<id>/edit/` has to be declared before
`listing/<id>/<slug>/`, or "edit" would be swallowed as a slug.
"""
from django.urls import path

from . import views

urlpatterns = [
    # browsing
    path('browse', views.property_list, name='property_list'),
    path('suggest/', views.search_suggest, name='search_suggest'),
    path('suggest/clear/', views.clear_recent_searches, name='clear_recent_searches'),
    path('categories', views.property_type, name='property_type'),
    path('compare/', views.compare, name='compare'),
    path('compare/clear/', views.clear_compare, name='clear_compare'),

    # listing something
    path('list-a-property', views.add_property, name='add_property'),
    path('list-a-property/<str:property_type>', views.add_property_data,
         name='add_property_data'),
    path('my-listings/', views.posted_properties, name='posted_properties'),

    # one listing — specific actions first
    path('listing/<int:property_id>/edit/', views.update_property, name='update_property'),
    path('listing/<int:property_id>/delete/', views.delete_property, name='delete_property'),
    path('listing/<int:property_id>/photos/', views.manage_images, name='manage_images'),
    path('listing/<int:property_id>/status/', views.change_status, name='change_status'),
    path('listing/<int:property_id>/insights/', views.property_analytics,
         name='property_analytics'),
    path('listing/<int:property_id>/save/', views.toggle_favourite, name='toggle_favourite'),
    path('listing/<int:property_id>/compare/', views.toggle_compare, name='toggle_compare'),
    path('listing/<int:property_id>/review/', views.write_review, name='write_review'),
    path('listing/<int:property_id>/book/', views.book_property, name='book_property'),
    path('listing/<int:property_id>/enquire/', views.start_conversation,
         name='start_conversation'),
    path('listing/<int:property_id>/report/', views.report_property, name='report_property'),
    path('listing/<int:property_id>/documents/', views.view_property_documents,
         name='view_property_documents'),
    # the file itself, streamed only after the permission check
    path('listing/<int:property_id>/documents/file/', views.property_document_file,
         name='property_document_file'),

    # …then the readable detail route and its id-only twin
    path('listing/<int:pk>/', views.property_detail, name='property_detail'),
    path('listing/<int:pk>/<slug:slug>/', views.property_detail, name='property_detail'),

    # photos
    path('photos/<int:image_id>/delete/', views.delete_image, name='delete_image'),
    path('photos/<int:image_id>/cover/', views.make_cover, name='make_cover'),

    # reviews
    path('reviews/<int:review_id>/delete/', views.delete_review, name='delete_review'),

    # saved places and searches
    path('saved/', views.favourites, name='favourites'),
    path('saved-searches/', views.saved_searches, name='saved_searches'),
    path('saved-searches/save/', views.save_search, name='save_search'),
    path('saved-searches/<int:search_id>/delete/', views.delete_saved_search,
         name='delete_saved_search'),

    # visits
    path('visits/', views.bookings, name='bookings'),
    path('visits/<int:booking_id>/<str:action>/', views.booking_action, name='booking_action'),

    # messaging
    path('messages/', views.inbox, name='inbox'),
    path('messages/<int:conversation_id>/', views.conversation, name='conversation'),
]
