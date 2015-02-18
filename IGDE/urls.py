from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.views.generic import TemplateView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'IGDE.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    # Foundation
    url(regex=r'^foundation/$',
        view=TemplateView.as_view(template_name="foundation/index.html"),
        name="foundation_index"),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^$', 'core.views.home', name='home'),
    url(r'^node_api$', 'core.views.node_api', name='node_api'),
    url(r'^login/$', 'django.contrib.auth.views.login', {'template_name': 'admin/login.html'}, name='login'),
    url(r'^logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}, name='logout'),
)

urlpatterns += staticfiles_urlpatterns()
