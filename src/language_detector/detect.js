#!/usr/bin/env node

const { ModelOperations } = require('@vscode/vscode-languagedetection');

async function detectLanguage(code) {
    const modelOperations = new ModelOperations();
    
    try {
        const results = await modelOperations.runModel(code);
        
        if (results && results.length > 0) {
            // Return top 5 results
            const topResults = results.slice(0, 5).map(r => ({
                language: r.languageId,
                confidence: r.confidence
            }));
            
            console.log(JSON.stringify({
                success: true,
                topResult: {
                    language: results[0].languageId,
                    confidence: results[0].confidence
                },
                allResults: topResults
            }));
        } else {
            console.log(JSON.stringify({
                success: true,
                topResult: {
                    language: 'plaintext',
                    confidence: 0
                },
                allResults: []
            }));
        }
    } catch (error) {
        console.error(JSON.stringify({
            success: false,
            error: error.message
        }));
        process.exit(1);
    }
}

// Read code from stdin
let inputCode = '';
process.stdin.setEncoding('utf8');

process.stdin.on('data', (chunk) => {
    inputCode += chunk;
});

process.stdin.on('end', async () => {
    await detectLanguage(inputCode);
});

// Handle errors
process.on('uncaughtException', (error) => {
    console.error(JSON.stringify({
        success: false,
        error: error.message
    }));
    process.exit(1);
});