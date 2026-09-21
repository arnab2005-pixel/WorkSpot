// MongoDB Initialization Script for PM-AJAY Voice Assistant
// Run this in mongosh: mongosh "mongodb://localhost:27017" scripts/init-mongo.js

db = db.getSiblingDB('pm_ajay');

// ============================================
// COLLECTIONS
// ============================================
db.createCollection('beneficiaries');
db.createCollection('nsqf_courses');
db.createCollection('training_centers');
db.createCollection('kiosks');
db.createCollection('sessions');  // For conversation session storage

// ============================================
// INDEXES
// ============================================

// --- Beneficiaries ---
db.beneficiaries.createIndex({ "phone_hash": 1 }, { unique: true, name: "idx_phone_hash_unique" });
db.beneficiaries.createIndex({ "demographics.district_code": 1 }, { name: "idx_district_code" });
db.beneficiaries.createIndex({ "detected_dialect": 1 }, { name: "idx_dialect" });
db.beneficiaries.createIndex({ "created_at": -1 }, { name: "idx_created_at_desc" });
db.beneficiaries.createIndex({ "profiling_slots.employment_intent": 1 }, { name: "idx_employment_intent" });
db.beneficiaries.createIndex({ "eligible_for_gia_asset_grant": 1 }, { name: "idx_gia_eligible" });
db.beneficiaries.createIndex({ "credit_desk_routing": 1 }, { name: "idx_credit_desk" });

// Compound indexes for common queries
db.beneficiaries.createIndex(
  { "demographics.district_code": 1, "detected_dialect": 1 },
  { name: "idx_district_dialect" }
);

// --- NSQF Courses ---
db.nsqf_courses.createIndex({ "qp_code": 1 }, { unique: true, name: "idx_qp_code_unique" });
db.nsqf_courses.createIndex({ "district_availability": 1 }, { name: "idx_district_availability" });
db.nsqf_courses.createIndex({ "sector": 1 }, { name: "idx_sector" });
db.nsqf_courses.createIndex({ "status": 1 }, { name: "idx_status" });
db.nsqf_courses.createIndex({ "min_education_tier": 1 }, { name: "idx_min_education_tier" });
db.nsqf_courses.createIndex({ "nsqf_level": 1 }, { name: "idx_nsqf_level" });
db.nsqf_courses.createIndex({ "training_center_id": 1 }, { name: "idx_training_center_id" });
db.nsqf_courses.createIndex({ "pathway_type": 1 }, { name: "idx_pathway_type" });
db.nsqf_courses.createIndex({ "target_occupations": 1 }, { name: "idx_target_occupations" });

// Compound filter indexes for vector search pre-filtering
db.nsqf_courses.createIndex(
  { "district_availability": 1, "status": 1, "min_education_tier": 1 },
  { name: "idx_vector_prefilter" }
);
db.nsqf_courses.createIndex(
  { "district_availability": 1, "sector": 1, "status": 1 },
  { name: "idx_district_sector_status" }
);

// Text search indexes
db.nsqf_courses.createIndex(
  { "course_name": "text", "course_name_indic": "text", "target_occupations": "text" },
  { name: "idx_text_search", weights: { course_name: 10, course_name_indic: 10, target_occupations: 5 } }
);

// --- Training Centers ---
db.training_centers.createIndex({ "center_id": 1 }, { unique: true, name: "idx_center_id_unique" });
db.training_centers.createIndex({ "district_code": 1 }, { name: "idx_tc_district_code" });
db.training_centers.createIndex({ "state": 1 }, { name: "idx_tc_state" });
db.training_centers.createIndex({ "center_type": 1 }, { name: "idx_tc_type" });
db.training_centers.createIndex({ "sectors_offered": 1 }, { name: "idx_tc_sectors" });
db.training_centers.createIndex({ "status": 1 }, { name: "idx_tc_status" });
db.training_centers.createIndex({ "block_name": 1 }, { name: "idx_tc_block" });

// Compound indexes
db.training_centers.createIndex(
  { "district_code": 1, "center_type": 1, "status": 1 },
  { name: "idx_tc_district_type_status" }
);

// Geospatial index for location-based queries
db.training_centers.createIndex(
  { "latitude": 1, "longitude": 1 },
  { name: "idx_tc_location_2d" }
);

// Text search
db.training_centers.createIndex(
  { "name": "text", "address": "text" },
  { name: "idx_tc_text_search" }
);

// --- Kiosks ---
db.kiosks.createIndex({ "kiosk_id": 1 }, { unique: true, name: "idx_kiosk_id_unique" });
db.kiosks.createIndex({ "district_code": 1 }, { name: "idx_kiosk_district" });
db.kiosks.createIndex({ "block_name": 1 }, { name: "idx_kiosk_block" });
db.kiosks.createIndex({ "state": 1 }, { name: "idx_kiosk_state" });
db.kiosks.createIndex({ "status": 1 }, { name: "idx_kiosk_status" });
db.kiosks.createIndex({ "location_type": 1 }, { name: "idx_kiosk_location_type" });
db.kiosks.createIndex({ "vle_phone": 1 }, { name: "idx_kiosk_vle_phone" });

// Compound
db.kiosks.createIndex(
  { "district_code": 1, "block_name": 1, "status": 1 },
  { name: "idx_kiosk_district_block_status" }
);

// Geospatial
db.kiosks.createIndex(
  { "latitude": 1, "longitude": 1 },
  { name: "idx_kiosk_location_2d" }
);

// --- Sessions (for conversation state) ---
db.sessions.createIndex({ "session_id": 1 }, { unique: true, name: "idx_session_id_unique" });
db.sessions.createIndex({ "call_uuid": 1 }, { name: "idx_call_uuid" });
db.sessions.createIndex({ "phone_hash": 1 }, { name: "idx_session_phone_hash" });
db.sessions.createIndex({ "current_state": 1 }, { name: "idx_session_state" });
db.sessions.createIndex({ "created_at": -1 }, { name: "idx_session_created_desc" });
db.sessions.createIndex({ "updated_at": -1 }, { name: "idx_session_updated_desc" });

// TTL index for automatic session cleanup (30 minutes)
db.sessions.createIndex(
  { "updated_at": 1 },
  { expireAfterSeconds: 1800, name: "idx_session_ttl" }
);

// ============================================
// ATLAS VECTOR SEARCH INDEX (for nsqf_courses)
// ============================================
// NOTE: This index must be created via Atlas UI or API, not mongosh
// See: https://www.mongodb.com/docs/atlas/atlas-vector-search/create-index/
//
// Index name: "nsqf_vector_index"
// Database: "pm_ajay"
// Collection: "nsqf_courses"
//
// Definition:
/*
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "course_embedding": {
        "type": "knnVector",
        "dimensions": 768,
        "similarity": "cosine"
      },
      "district_availability": { "type": "filter" },
      "min_education_tier": { "type": "filter" },
      "status": { "type": "filter" },
      "sector": { "type": "filter" },
      "nsqf_level": { "type": "filter" },
      "pathway_type": { "type": "filter" }
    }
  }
}
*/

// ============================================
// SAMPLE DATA (run seed_mock_data.py for full dataset)
// ============================================

// Helper to generate normalized dummy 768-dim vector
function generateEmbedding(seed) {
  var vec = [];
  var sumSq = 0;
  for (var i = 0; i < 768; i++) {
    var val = Math.sin(seed + i);
    vec.push(val);
    sumSq += val * val;
  }
  var norm = Math.sqrt(sumSq);
  for (var j = 0; j < 768; j++) {
    vec[j] = vec[j] / norm;
  }
  return vec;
}

// Seed a few essential courses if collection is empty
if (db.nsqf_courses.countDocuments() === 0) {
  print("Seeding initial NSQF courses...");
  
  db.nsqf_courses.insertMany([
    // Apparel sector
    {
      qp_code: "AMH/Q0301",
      course_name: "Self Employed Tailor",
      course_name_indic: "स्व-रोज़गार दर्जी",
      sector: "Apparel, Made-ups & Home Furnishing",
      nsqf_level: 4,
      min_education_tier: 1,
      is_residential: false,
      district_availability: ["UP_VARANASI", "UP_PRAYAGRAJ", "BR_PATNA", "UP_CHANDAULI", "UP_LUCKNOW"],
      duration_hours: 360,
      stipend_per_month: 1500,
      training_center: "Varanasi Skill Center, Cantt",
      status: "ACTIVE",
      course_embedding: generateEmbedding(1.0),
      created_at: new Date(),
      pathway_type: "VOCATIONAL_TRAINING",
      target_occupations: ["सिलाई", "टेलर", "दर्जी", "tailoring", "stitching"],
      tags: ["apparel", "uttar_pradesh", "varanasi"]
    },
    {
      qp_code: "AMH/Q1001",
      course_name: "Hand Embroiderer",
      course_name_indic: "कसीदाकारी कारीगर",
      sector: "Apparel, Made-ups & Home Furnishing",
      nsqf_level: 3,
      min_education_tier: 0,
      is_residential: false,
      district_availability: ["UP_VARANASI", "BR_PATNA", "UP_PRAYAGRAJ"],
      duration_hours: 300,
      stipend_per_month: 1500,
      training_center: "Rural ITI Center, Chiraigaon",
      status: "ACTIVE",
      course_embedding: generateEmbedding(2.0),
      created_at: new Date(),
      pathway_type: "VOCATIONAL_TRAINING",
      target_occupations: ["कढ़ाई", "कसीदाकारी", "embroidery", "needlework"],
      tags: ["apparel", "bihar", "patna"]
    },
    // Construction sector
    {
      qp_code: "CON/Q0101",
      course_name: "Assistant Mason",
      course_name_indic: "सहायक राजमिस्त्री",
      sector: "Construction",
      nsqf_level: 2,
      min_education_tier: 0,
      is_residential: true,
      district_availability: ["UP_VARANASI", "UP_LUCKNOW", "BR_PATNA", "MP_BHOPAL", "RJ_JAIPUR"],
      duration_hours: 400,
      stipend_per_month: 2000,
      training_center: "Construction Guild Center, Varanasi",
      status: "ACTIVE",
      course_embedding: generateEmbedding(3.0),
      created_at: new Date(),
      pathway_type: "VOCATIONAL_TRAINING",
      target_occupations: ["राजमिस्त्री", "मेसन", "masonry", "construction"],
      tags: ["construction", "multi_state"]
    },
    // Electronics
    {
      qp_code: "ELE/Q3501",
      course_name: "Mobile Phone Hardware Repair Technician",
      course_name_indic: "मोबाइल फोन हार्डवेयर मरम्मत तकनीशियन",
      sector: "Electronics & Hardware",
      nsqf_level: 4,
      min_education_tier: 2,
      is_residential: false,
      district_availability: ["UP_VARANASI", "UP_LUCKNOW", "UP_KANPUR", "BR_PATNA", "MP_INDORE", "MH_PUNE"],
      duration_hours: 300,
      stipend_per_month: 1800,
      training_center: "Digital Skills Center, Varanasi",
      status: "ACTIVE",
      course_embedding: generateEmbedding(4.0),
      created_at: new Date(),
      pathway_type: "VOCATIONAL_TRAINING",
      target_occupations: ["मोबाइल मरम्मत", "mobile repair", "phone repair", "स्मार्टफोन रिपेयर"],
      tags: ["electronics", "digital_skills"]
    },
    // Beauty & Wellness
    {
      qp_code: "BWS/Q0201",
      course_name: "Hair Stylist",
      course_name_indic: "हेयर स्टाइलिस्ट",
      sector: "Beauty & Wellness",
      nsqf_level: 4,
      min_education_tier: 1,
      is_residential: false,
      district_availability: ["UP_VARANASI", "UP_LUCKNOW", "BR_PATNA", "MP_BHOPAL", "RJ_JAIPUR", "MH_MUMBAI"],
      duration_hours: 360,
      stipend_per_month: 1500,
      training_center: "Beauty Academy, Varanasi",
      status: "ACTIVE",
      course_embedding: generateEmbedding(5.0),
      created_at: new Date(),
      pathway_type: "VOCATIONAL_TRAINING",
      target_occupations: ["ब्यूटीशियन", "ब्यूटी पार्लर", "beauty", "parlor", "makeup", "हेयर स्टाइलिस्ट"],
      tags: ["beauty_wellness", "women_focused"]
    },
    // Agriculture
    {
      qp_code: "AGR/Q0201",
      course_name: "Dairy Farmer",
      course_name_indic: "डेयरी किसान",
      sector: "Agriculture",
      nsqf_level: 4,
      min_education_tier: 0,
      is_residential: false,
      district_availability: ["UP_VARANASI", "UP_CHANDAULI", "BR_GAYA", "BR_MUZAFFARPUR", "MP_JABALPUR", "RJ_BIKANER"],
      duration_hours: 300,
      stipend_per_month: 1500,
      training_center: "Dairy Training Center, Chandauli",
      status: "ACTIVE",
      course_embedding: generateEmbedding(6.0),
      created_at: new Date(),
      pathway_type: "VOCATIONAL_TRAINING",
      target_occupations: ["डेयरी", "पशुपालन", "dairy", "animal husbandry", "गाय भैंस पालन"],
      tags: ["agriculture", "rural_livelihood"]
    },
    // IT-ITeS
    {
      qp_code: "SSC/Q0101",
      course_name: "Domestic Data Entry Operator",
      course_name_indic: "डेटा एंट्री ऑपरेटर",
      sector: "IT-ITeS",
      nsqf_level: 4,
      min_education_tier: 2,
      is_residential: false,
      district_availability: ["UP_VARANASI", "UP_LUCKNOW", "UP_KANPUR", "BR_PATNA", "MP_BHOPAL", "MH_PUNE", "WB_KOLKATA"],
      duration_hours: 200,
      stipend_per_month: 1200,
      training_center: "IT Skill Hub, Varanasi",
      status: "ACTIVE",
      course_embedding: generateEmbedding(7.0),
      created_at: new Date(),
      pathway_type: "VOCATIONAL_TRAINING",
      target_occupations: ["कंप्यूटर", "डेटा एंट्री", "computer", "data entry", "typing", "ऑफिस वर्क"],
      tags: ["it_ites", "digital_literacy"]
    },
    // Food Processing
    {
      qp_code: "FIC/Q1001",
      course_name: "Bakery & Confectionery Technician",
      course_name_indic: "बेकरी और कन्फेक्शनरी तकनीशियन",
      sector: "Food Processing",
      nsqf_level: 4,
      min_education_tier: 1,
      is_residential: false,
      district_availability: ["UP_VARANASI", "UP_LUCKNOW", "BR_PATNA", "MP_INDORE", "RJ_JAIPUR", "MH_NAGPUR"],
      duration_hours: 300,
      stipend_per_month: 1500,
      training_center: "Food Craft Institute, Varanasi",
      status: "ACTIVE",
      course_embedding: generateEmbedding(8.0),
      created_at: new Date(),
      pathway_type: "VOCATIONAL_TRAINING",
      target_occupations: ["बेकरी", "केक", "bakery", "confectionery", "मिठाई बनाने वाला"],
      tags: ["food_processing", "entrepreneurship"]
    },
    // Solar/Energy
    {
      qp_code: "ELE/Q4601",
      course_name: "Solar Panel Installation Technician",
      course_name_indic: "सौर पैनल स्थापना तकनीशियन",
      sector: "Electronics & Hardware",
      nsqf_level: 4,
      min_education_tier: 1,
      is_residential: false,
      district_availability: ["UP_VARANASI", "UP_LUCKNOW", "BR_PATNA", "MP_BHOPAL", "RJ_JAIPUR", "MH_AURANGABAD"],
      duration_hours: 240,
      stipend_per_month: 2000,
      training_center: "Green Energy Training Center, Varanasi",
      status: "ACTIVE",
      course_embedding: generateEmbedding(9.0),
      created_at: new Date(),
      pathway_type: "VOCATIONAL_TRAINING",
      target_occupations: ["सौर ऊर्जा", "solar", "solar panel", "renewable energy", "सोलर पैनल लगाने वाला"],
      tags: ["green_energy", "electronics", "future_skills"]
    },
    // Healthcare
    {
      qp_code: "HSS/Q0101",
      course_name: "General Duty Assistant",
      course_name_indic: "सामान्य ड्यूटी सहायक",
      sector: "Healthcare",
      nsqf_level: 4,
      min_education_tier: 2,
      is_residential: false,
      district_availability: ["UP_VARANASI", "UP_LUCKNOW", "BR_PATNA", "MP_BHOPAL", "WB_KOLKATA"],
      duration_hours: 400,
      stipend_per_month: 2000,
      training_center: "Healthcare Skill Center, Varanasi",
      status: "ACTIVE",
      course_embedding: generateEmbedding(10.0),
      created_at: new Date(),
      pathway_type: "VOCATIONAL_TRAINING",
      target_occupations: ["नर्सिंग सहायक", "हॉस्पिटल अटेंडेंट", "healthcare assistant", "patient care"],
      tags: ["healthcare", "employment"]
    },
  ]);
  
  print("✅ Initial NSQF courses seeded.");
}

// Print summary
print("\n📊 Database initialized with collections:");
print("   - beneficiaries");
print("   - nsqf_courses");
print("   - training_centers");
print("   - kiosks");
print("   - sessions");
print("\n🔍 Indexes created for all collections");
print("\n📝 Note: Run 'python scripts/seed_mock_data.py' for full mock dataset");
print("   with 250+ training centers, 500+ courses, 50 beneficiaries, 150+ kiosks");
print("\n🚀 Atlas Vector Search index 'nsqf_vector_index' must be created via Atlas UI");