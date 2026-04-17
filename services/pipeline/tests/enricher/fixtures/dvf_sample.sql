INSERT INTO dvf_transactions (
  date_mutation,
  valeur_fonciere,
  type_local,
  surface_reelle_bati,
  adresse_numero,
  adresse_nom_voie,
  code_postal,
  commune,
  geom
) VALUES (
  DATE '2025-03-01',
  580000,
  'Appartement',
  80,
  '10',
  'Rue Oberkampf',
  '75011',
  'Paris',
  ST_GeomFromText('POINT(2.378 48.864)', 4326)
);
