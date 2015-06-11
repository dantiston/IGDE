from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.views.generic import TemplateView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = patterns('',
    # Foundation
    url(regex=r'^foundation/$',
        view=TemplateView.as_view(template_name="foundation/index.html"),
        name="foundation_index"),

    # IGDE
    url(r'^$', 'wxlui.views.home', name='home'),
    url(r'^parse$', 'wxlui.views.parse', name='parse'),
    url(r'^request$', 'wxlui.views.request', name='request'),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^login/$', 'django.contrib.auth.views.login', {'template_name': 'admin/login.html'}, name='login'),
    url(r'^logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}, name='logout'),
)

urlpatterns += staticfiles_urlpatterns()
