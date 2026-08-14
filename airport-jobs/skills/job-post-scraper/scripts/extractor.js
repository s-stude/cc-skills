const {
          createTitleSlug,
          createSourceRef,
          calculateExpiryDate,
          generateJobUID,
          slugify
      }              = require( './utils' );
const { loadConfig } = require( './config' );

function buildExtractionPrompt( url, orgName ) {
    return `Extract job posting details from this page and return ONLY valid JSON with no additional text or explanation.

Required fields:
- title: exact job title as shown on page
- location_text: city/country or region (e.g., "Nairobi, Kenya", "Remote", "London, UK")
- work_mode: must be one of: "on-site", "hybrid", "remote"
- regions: array from: "africa", "asia", "europe", "latin-america", "middle-east", "north-america", "oceania"
- countries: array of country slugs (lowercase, hyphenated, e.g., "kenya", "united-kingdom")
- cause_areas: array from: "human-rights", "climate", "poverty", "education", "global-health", "children-youth", "animal-welfare"
- seniority: must be one of: "entry", "mid", "senior", "executive"
- contract_type: must be one of: "full-time", "part-time", "contract", "consultant"
- travel_required: boolean (true or false)
- compensation_text: salary/compensation info or "Not specified"
- description_markdown: full job description formatted in Markdown with ## headings for sections
- apply_url: application URL or mailto: email

Organization: ${ orgName }
Page URL: ${ url }

Return ONLY the JSON object, no other text.`;
}

function validateJobData( data ) {
    const required = [
        'title',
        'location_text',
        'work_mode',
        'regions',
        'countries',
        'cause_areas',
        'seniority',
        'contract_type',
        'travel_required',
        'description_markdown',
        'apply_url'
    ];

    const missing = required.filter( field => data[field] === undefined || data[field] === null );

    if (missing.length > 0) {
        return {
            valid: false,
            missing
        };
    }

    return { valid: true };
}

function mapToSchema( extractedData, orgData, url ) {
    const cfg = loadConfig();
    const now = new Date().toISOString();
    const uid = generateJobUID();

    const locationSlug = slugify( extractedData.location_text );
    const titleSlug    = createTitleSlug(
        extractedData.title,
        orgData.name,
        extractedData.location_text
    );

    // Primary cause area is the first element of cause_areas array
    const primaryCauseArea = extractedData.cause_areas && extractedData.cause_areas.length > 0
        ? extractedData.cause_areas[0]
        : null;

    return {
        meta                : {
            uid,
            verification_level: 'verified_source',
            is_deleted        : false,
            archived_at       : null,
            published_at      : now,
            expires_at        : null,
            created_at        : now,
            updated_at        : now
        },
        org                 : {
            uid: orgData.uid
        },
        source              : {
            source_ref: createSourceRef( orgData.slug, extractedData.title ),
            source_url: url
        },
        apply_url           : extractedData.apply_url,
        title               : extractedData.title,
        title_slug          : titleSlug,
        location_text       : extractedData.location_text,
        location_slug       : locationSlug,
        work_mode           : extractedData.work_mode,
        regions             : extractedData.regions,
        countries           : extractedData.countries,
        cause_areas         : extractedData.cause_areas,
        primary_cause_area  : primaryCauseArea,
        seniority           : extractedData.seniority,
        contract_type       : extractedData.contract_type,
        travel_required     : extractedData.travel_required,
        compensation_text   : extractedData.compensation_text || 'Not specified',
        description_markdown: extractedData.description_markdown
    };
}

module.exports = {
    buildExtractionPrompt,
    validateJobData,
    mapToSchema
};
