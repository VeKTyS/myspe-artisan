#
# entity.py
#
# Résolution de la société (entreprise) rattachée à une torréfaction.
#
# Le desktop connaît les sociétés par leur slug — `entity_hr_id` servi par
# artisan-api dans /v1/acoffees, p.ex. 'esperanza' — jamais par leur UUID
# Supabase. C'est ce slug qui part avec l'envoi et qui est écrit dans le .alog.
#
# Ce module est volontairement pur (ni Qt, ni réseau, ni état global) : la
# cascade est la seule règle métier du fichier, et c'est elle qui décide si une
# torréfaction sera correctement rattachée ou finira sur les fiches fourre-tout
# du serveur (« Grain inconnu », aucun décrément de stock).

from typing import Final

# Séparateur entre le code de magasin et le slug de la société dans un hr_id
# composite ('L1002@esperanza'). Identique à plus.stock.
ENTITY_SEPARATOR: Final[str] = '@'


def slug_from_store_hr_id(hr_id: str | None) -> str | None:
    """Slug de la société portée par un hr_id de magasin composite.

    'L1002@esperanza' -> 'esperanza'. Un code nu ('L1002', 'DESKTOP') n'en porte
    aucune : le même code peut appartenir à plusieurs sociétés, deviner serait
    précisément l'erreur que ce module existe pour éviter.
    """
    if not hr_id or ENTITY_SEPARATOR not in hr_id:
        return None
    # rsplit : le slug est le DERNIER segment (un code peut contenir un '@')
    slug = hr_id.rsplit(ENTITY_SEPARATOR, 1)[1].strip().lower()
    return slug or None


def resolve_entity_slug(
    store_hr_id: str | None,
    selected_slug: str | None,
    profile_slug: str | None,
) -> str | None:
    """Cascade de résolution, première valeur non vide gagnante :

    1. le magasin choisi, dont le hr_id composite fait foi (c'est lui qui porte
       le stock à décrémenter) ;
    2. la société choisie dans le sélecteur des Propriétés de torréfaction ;
    3. la valeur déjà présente dans le profil chargé (édition d'un .alog
       existant, qui garde le rattachement d'origine).

    Renvoie None quand rien ne résout : l'appelant doit alors demander la
    société à l'opérateur plutôt que d'envoyer la torréfaction sans
    rattachement.
    """
    from_store = slug_from_store_hr_id(store_hr_id)
    if from_store:
        return from_store
    if selected_slug and selected_slug.strip():
        return selected_slug.strip().lower()
    if profile_slug and profile_slug.strip():
        return profile_slug.strip().lower()
    return None
