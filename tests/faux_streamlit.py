"""FAUX module streamlit pour tester le parcours sans Streamlit (non installable dans le bac à sable).

Il imite les comportements de Streamlit qui comptent pour ce code :
  - l'état d'un widget (clé `key`) est SUPPRIMÉ en fin d'exécution si le widget n'a pas été affiché,
    sauf si la clé a été réaffectée pendant l'exécution (motif `S[k] = S[k]` documenté) ;
  - affecter `session_state[key]` APRÈS que le widget de même clé a été affiché dans la même exécution
    est une erreur ;
  - les callbacks `on_click` s'exécutent après l'exécution qui a vu le clic, avant la suivante ;
  - `st.rerun()` interrompt l'exécution et en relance une autre.
Ce n'est pas Streamlit : les noms d'API utilisés ont été vérifiés dans la documentation, mais ce
faux module ne prouve pas que l'affichage réel est correct.
"""
from __future__ import annotations

import contextlib
import types
from collections.abc import MutableMapping


class Arret(Exception):
    pass


class Relance(Exception):
    pass


class ErreurStreamlit(Exception):
    pass


class Etat(MutableMapping):
    def __init__(self, faux):
        object.__setattr__(self, "_d", {})
        object.__setattr__(self, "_faux", faux)

    def __getitem__(self, k):
        return self._d[k]

    def __setitem__(self, k, v):
        f = self._faux
        if f.phase == "script":
            if k in f.rendus:
                raise ErreurStreamlit(f"« {k} » modifié après l'affichage de son widget dans la même exécution")
            f.assignes.add(k)
        self._d[k] = v

    def __delitem__(self, k):
        del self._d[k]

    def __iter__(self):
        return iter(list(self._d))

    def __len__(self):
        return len(self._d)

    def __getattr__(self, k):
        try:
            return self._d[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v


class FauxSt(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = Etat(self)
        self.secrets = {}
        self.phase = "hors"
        self.rendus, self.assignes, self.cles_widgets = set(), set(), set()
        self.clics, self.en_attente = set(), []
        self.sortie = []                  # (genre, texte) dans l'ordre d'affichage
        self.boutons = {}                 # id -> désactivé ?
        self.widgets = {}                 # clé -> options (pour contrôler les valeurs)

    # ------------------------------------------------------------ cycle d'exécution
    def debut(self):
        self.sortie, self.en_attente, self.boutons = [], [], {}
        self.rendus, self.assignes = set(), set()
        self.phase = "script"

    def fin(self):
        self.phase = "hors"
        for cle in list(self.cles_widgets):
            if cle in self.session_state._d and cle not in self.rendus and cle not in self.assignes:
                del self.session_state._d[cle]

    # ------------------------------------------------------------ affichage
    def _ecrit(self, genre):
        return lambda texte="", *a, **k: self.sortie.append((genre, str(texte)))

    def __getattr__(self, nom):
        if nom in {"title", "header", "subheader", "markdown", "caption", "code", "info", "success", "warning",
                   "error", "text", "write"}:
            return self._ecrit(nom)
        if nom in {"set_page_config", "divider"}:
            return lambda *a, **k: self.sortie.append((nom, str(a[:1])))
        raise AttributeError(nom)

    def image(self, source, *a, **k):
        self.sortie.append(("image", str(source)))

    def progress(self, valeur, text=""):
        assert 0 <= valeur <= 1, valeur
        self.sortie.append(("progress", text))

    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [contextlib.nullcontext() for _ in range(n)]

    def container(self, *a, **k):
        return contextlib.nullcontext()

    def expander(self, label, *a, **k):
        self.sortie.append(("expander", label))
        return contextlib.nullcontext()

    def spinner(self, *a, **k):
        return contextlib.nullcontext()

    @property
    def sidebar(self):
        return contextlib.nullcontext()

    def stop(self):
        raise Arret()

    def rerun(self):
        raise Relance()

    def dialog(self, titre, **k):
        def decorateur(fonction):
            def appelee(*a, **kw):
                self.sortie.append(("dialog", titre))
                return fonction(*a, **kw)
            return appelee
        return decorateur

    # ------------------------------------------------------------ widgets
    def _widget(self, cle, defaut, options=None):
        if cle is None:
            return defaut
        if self.phase == "script" and cle in self.rendus:
            raise ErreurStreamlit(f"clé de widget dupliquée : {cle}")
        self.cles_widgets.add(cle)
        self.rendus.add(cle)
        if cle not in self.session_state._d:
            self.session_state._d[cle] = defaut
        valeur = self.session_state._d[cle]
        if options is not None:
            for v in (valeur if isinstance(valeur, list) else [valeur]):
                assert v in options, f"{cle} : valeur « {v} » absente des options"
        return valeur

    def text_area(self, label, value="", key=None, **k):
        return self._widget(key, value)

    text_input = text_area

    def slider(self, label, mini, maxi, value=None, key=None, **k):
        return self._widget(key, mini if value is None else value)

    def checkbox(self, label, value=False, key=None, **k):
        self.sortie.append(("checkbox", label))
        return self._widget(key, value)

    def selectbox(self, label, options, index=0, key=None, **k):
        return self._widget(key, options[index], list(options))

    def pills(self, label, options, selection_mode="single", default=None, key=None, **k):
        self.sortie.append(("pills", " | ".join(options)))
        defaut = list(default or []) if selection_mode == "multi" else default
        return self._widget(key, defaut, list(options))

    def button(self, label, key=None, on_click=None, args=None, type=None, disabled=False, **k):
        ident = key or label
        self.boutons[ident] = disabled
        self.sortie.append(("button", label))
        if ident in self.clics and not disabled:
            if on_click:
                self.en_attente.append((on_click, tuple(args or ())))
            return True
        return False

    def download_button(self, label, data=None, file_name=None, mime=None, key=None, **k):
        self.telechargements = getattr(self, "telechargements", {})
        self.telechargements[key or label] = (file_name, mime, data)
        self.sortie.append(("download", label))
        return False

    def textes(self, *genres):
        return "\n".join(t for g, t in self.sortie if not genres or g in genres)
