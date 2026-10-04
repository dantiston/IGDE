from django.urls import path, re_path

from core import views

urlpatterns = [
    path("api/status", views.status),
    path("api/settings", views.settings_view),
    path("api/settings/test-ace", views.test_ace),
    path("api/fs/roots", views.fs_roots),
    path("api/fs/list", views.fs_list),
    path("api/fs/file", views.fs_file),
    path("api/fs/detect-grammar", views.fs_detect_grammar),
    path("api/grammars", views.grammars),
    path("api/grammars/<int:gid>", views.grammar_detail),
    path("api/grammars/<int:gid>/activate", views.grammar_activate),
    path("api/grammars/<int:gid>/compile", views.grammar_compile),
    path("api/grammars/<int:gid>/files", views.grammar_files),
    path("api/parse", views.parse),
    path("api/generate", views.generate),
    path("api/processes", views.processes),
    path("api/processes/stop", views.processes_stop),
    path("api/tfs/parse", views.tfs_parse),
    path("api/tfs/node", views.tfs_node),
    path("api/tfs/lookup", views.tfs_lookup),
    path("api/tfs/hierarchy", views.tfs_hierarchy),
    path("api/tfs/unify", views.tfs_unify),
    path("assets/<path:path>", views.assets),
    re_path(r"^(?!api/)(?P<path>.*)$", views.spa),
]
