from django.urls import path

from . import views

urlpatterns = [
    path('add_property', views.add_property, name='add_property'),
    path('add_property_data/<str:property_type>', views.add_property_data,
         name='add_property_data'),
    path('property_list', views.property_list, name='property_list'),
    path('property_type', views.property_type, name='property_type'),
    path('property_list/<int:pk>', views.property_detail, name='property_detail'),
    path('posted-properties/', views.posted_properties, name='posted_properties'),
    path('update-property/<int:property_id>/', views.update_property, name='update_property'),
    path('property/delete/<int:property_id>/', views.delete_property, name='delete_property'),
    path('property/<int:property_id>/documents/', views.view_property_documents,
         name='view_property_documents'),
    # the file itself, streamed only after the permission check
    path('property/<int:property_id>/documents/file/', views.property_document_file,
         name='property_document_file'),

    # --- new in v2 -------------------------------------------------------
    # images
    path('<int:property_id>/images/', views.manage_images, name='manage_images'),
    path('images/<int:image_id>/delete/', views.delete_image, name='delete_image'),
    path('images/<int:image_id>/cover/', views.make_cover, name='make_cover'),
    # status
    path('<int:property_id>/status/', views.change_status, name='change_status'),
    path('<int:property_id>/analytics/', views.property_analytics, name='property_analytics'),
    # favourites
    path('favourites/', views.favourites, name='favourites'),
    path('<int:property_id>/favourite/', views.toggle_favourite, name='toggle_favourite'),
    # compare
    path('compare/', views.compare, name='compare'),
    path('<int:property_id>/compare/', views.toggle_compare, name='toggle_compare'),
    path('compare/clear/', views.clear_compare, name='clear_compare'),
    # reviews
    path('<int:property_id>/review/', views.write_review, name='write_review'),
    path('review/<int:review_id>/delete/', views.delete_review, name='delete_review'),
    # bookings
    path('<int:property_id>/book/', views.book_property, name='book_property'),
    path('bookings/', views.bookings, name='bookings'),
    path('bookings/<int:booking_id>/<str:action>/', views.booking_action, name='booking_action'),
    # messaging
    path('inbox/', views.inbox, name='inbox'),
    path('<int:property_id>/enquire/', views.start_conversation, name='start_conversation'),
    path('inbox/<int:conversation_id>/', views.conversation, name='conversation'),
    # saved searches
    path('saved-searches/', views.saved_searches, name='saved_searches'),
    path('saved-searches/save/', views.save_search, name='save_search'),
    path('saved-searches/<int:search_id>/delete/', views.delete_saved_search,
         name='delete_saved_search'),
]
