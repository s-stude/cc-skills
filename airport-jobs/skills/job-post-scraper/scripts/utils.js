const path   = require( 'path' );
const crypto = require( 'crypto' );

// Import shared utilities from plugin level
const { generateShortUID }                          = require( './generate-uid.js' );
const { slugify, createTitleSlug, createSourceRef } = require( './slug-utils.js' );

/**
 * Generates a unique job post UID
 * @returns {string} Job UID with 'jp' prefix (e.g., "jp_a8f2k9m4")
 */
function generateJobUID() {
    return generateShortUID( 'jp' );
}

/**
 * Generates a filename from a UID
 * @param {string} uid - The job UID
 * @returns {string} Filename (e.g., "jp_a8f2k9m4.json")
 */
function generateFilename( uid ) {
    return `${ uid }.json`;
}

module.exports = {
    // Re-export shared utilities
    slugify,
    createTitleSlug,
    createSourceRef,
    // Local utilities
    generateShortUID,
    generateJobUID,
    generateFilename,
};
