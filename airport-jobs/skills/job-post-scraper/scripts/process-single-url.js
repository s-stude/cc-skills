#!/usr/bin/env node

/**
 * CLI script for testing single URL processing
 * Usage: node process-single-url.js <url> [org-uid]
 */

const { findOrgByUrl, getOrgData } = require( './file-manager' );
const { buildExtractionPrompt }    = require( './extractor' );

async function main() {
    const url            = process.argv[2];
    const orgUidOverride = process.argv[3];

    if (!url) {
        console.error( 'Usage: node process-single-url.js <url> [org-uid]' );
        process.exit( 1 );
    }

    // Auto-detect org or use override
    let orgResult;
    if (orgUidOverride) {
        const orgData = getOrgData( orgUidOverride );
        if (orgData) {
            orgResult = { found: true, uid: orgUidOverride, name: orgData.name };
        } else {
            console.error( `Error: Organization not found: ${ orgUidOverride }` );
            process.exit( 1 );
        }
    } else {
        orgResult = findOrgByUrl( url );
    }

    // Build extraction prompt
    const prompt = buildExtractionPrompt( url, orgResult.name || 'Unknown Organization' );

    // Output results
    const output = {
        url,
        org: orgResult,
        prompt
    };

    console.log( JSON.stringify( output, null, 2 ) );
}

main().catch( err => {
    console.error( 'Error:', err.message );
    process.exit( 1 );
} );
