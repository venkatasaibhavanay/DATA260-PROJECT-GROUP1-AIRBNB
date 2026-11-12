// Runs once, on the first start of an empty MongoDB volume.
// Collections are created by each owning service; this only marks initialisation.
const dbName = process.env.MONGO_INITDB_DATABASE || "airbnb_group1";
const appDb = db.getSiblingDB(dbName);
appDb.createCollection("schema_info");
appDb.schema_info.insertOne({ component: "bootstrap", version: "0.1.0", applied_at: new Date() });
