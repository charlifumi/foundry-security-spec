# NOTICE — Provenance & attributions

**Forge** est une œuvre dérivée de démonstration. Il n'est pas affilié à Cisco, GitHub ni CoSAI,
et n'est pas un produit officiel de ces organisations.

## Amont

- **Foundry Security Spec** — © Cisco Systems, Inc. Spécification ouverte d'évaluation de
  sécurité agentique. Auteurs originaux : Theo Morales (@kh0rvus), John Allbritten (@jallbrit).
  <https://github.com/CiscoDevNet/foundry-security-spec>
  Ce dépôt **dérive** de cette seed : `spec.md` et `clarifications.md` sont la sortie du workflow
  `/speckit.clarify` + `/speckit.specify` appliqué à la seed ; `.specify/memory/constitution.md`
  reprend la constitution de la seed.

- **spec-kit** — © GitHub, Inc. Workflow de développement *spec-driven*.
  <https://github.com/github/spec-kit>

- **Project CodeGuard** — maintenu sous CoSAI (OASIS). Format de règles de sécurité pour agents
  de codage IA, à l'origine publié par Cisco. Utilisé ici comme format du corpus de règles de
  détection (`rules/`). <https://project-codeguard.org> · <https://github.com/cosai-oasis/project-codeguard>

## Marques

« Cisco », « Foundry », « GitHub », « CodeGuard » et « CoSAI » appartiennent à leurs détenteurs
respectifs. Leur mention décrit la filiation technique de ce projet, sans revendication
d'affiliation ni d'endossement.

## Sécurité

La cible `targets/vulnshop` est **intentionnellement vulnérable** à des fins de démonstration.
Elle ne doit jamais être déployée hors d'un environnement jetable et isolé.
