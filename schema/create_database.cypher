// Skapa en NY tom databas för det här projektet (slipper wipe av gammal graf).
//
// Kör i Neo4j Browser:
// 1) Välj översta DB-rutan → "system" (krävs i Neo4j 5 för CREATE DATABASE).
// 2) Klistra in raden nedan och kör.
// 3) Sätt i .env: NEO4J_DATABASE=exjobbet_index  (eller valfritt namn du väljer)
//
// Kräver Neo4j som stödjer flera databaser (t.ex. Enterprise). Annars använd
// standarddatabasen neo4j och töm med MATCH (n) DETACH DELETE n.

CREATE DATABASE exjobbet_index IF NOT EXISTS WAIT;
