// MongoDB Initialization Script for PM-AJAY Voice Assistant
db = db.getSiblingDB('pm_ajay');

// Create collections
db.createCollection('beneficiaries');
db.createCollection('nsqf_courses');

// Create standard indexes
db.beneficiaries.createIndex({ "phone_hash": 1 }, { unique: true });
db.beneficiaries.createIndex({ "demographics.district_code": 1 });
db.beneficiaries.createIndex({ "created_at": -1 });

db.nsqf_courses.createIndex({ "qp_code": 1 }, { unique: true });
db.nsqf_courses.createIndex({ "district_availability": 1, "status": 1, "min_education_tier": 1 });

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

// Seed NSQF Courses
db.nsqf_courses.insertMany([
  {
    qp_code: "AMH/Q0301",
    course_name: "Self Employed Tailor",
    course_name_indic: "स्व-रोज़गार दर्जी",
    sector: "Apparel, Made-ups & Home Furnishing",
    nsqf_level: 4,
    min_education_tier: 1,
    is_residential: false,
    district_availability: ["UP_VARANASI", "UP_PRAYAGRAJ", "BR_PATNA", "UP_CHANDAULI"],
    duration_hours: 360,
    stipend_per_month: 1500,
    training_center: "Varanasi Skill Center, Cantt",
    status: "ACTIVE",
    course_embedding: generateEmbedding(1.0),
    created_at: new Date()
  },
  {
    qp_code: "AMH/Q1001",
    course_name: "Hand Embroiderer",
    course_name_indic: "कसीदाकारी कारीगर",
    sector: "Apparel, Made-ups & Home Furnishing",
    nsqf_level: 3,
    min_education_tier: 0,
    is_residential: false,
    district_availability: ["UP_VARANASI", "BR_PATNA"],
    duration_hours: 300,
    stipend_per_month: 1500,
    training_center: "Rural ITI Center, Chiraigaon",
    status: "ACTIVE",
    course_embedding: generateEmbedding(2.0),
    created_at: new Date()
  },
  {
    qp_code: "CON/Q0101",
    course_name: "Assistant Mason",
    course_name_indic: "सहायक राजमिस्त्री",
    sector: "Construction",
    nsqf_level: 2,
    min_education_tier: 0,
    is_residential: true,
    district_availability: ["UP_VARANASI", "UP_LUCKNOW", "BR_PATNA"],
    duration_hours: 400,
    stipend_per_month: 2000,
    training_center: "Construction Guild Center, Varanasi",
    status: "ACTIVE",
    course_embedding: generateEmbedding(3.0),
    created_at: new Date()
  }
]);

print("PM-AJAY MongoDB initialized with seed courses.");
