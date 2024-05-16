'use strict';
/**
 * @module clippy
 */

const utils = require('../lib/utils');
const debug = require('debug')('sockbot:plugins:summoner');
const { NodeHtmlMarkdown } = require('node-html-markdown');
const fs = require('fs');
const path = require('path');

function surroundMentionsWithColons(content) {
    return content.replace(/(^|\W)@([a-zA-Z0-9_-]{1,64})/g, '$1:$2:');
}

async function moderateContent(content) {
    const response = await openai.createModeration({ input: content });
    const moderation_result = response.data.results[0].flagged;
    if (moderation_result) {
        debug(`Content flagged: ${content}`);
    }
    return !moderation_result;
}

// system_message is initialized with the contents of the file ../system_message.txt

const sysmsgpath = path.join(__dirname, 'system_message.txt');

let system_message = fs.readFileSync(sysmsgpath, 'utf8');

let model = process.env.OPENROUTER_MODEL || "meta-llama/llama-3-70b-instruct";
let character_limit = process.env.OPENROUTER_CHARACTER_LIMIT || 25000;

const system_message_complement = `
You're talking in a forum, and your answers should follow the markdown format, without any links or images.
All usernames are prefixed with an '@' character.

Your username in the forum is 'clippy'.`;

function format_system_message() {
    return {
        role: "system",
        content: system_message + '\n' + system_message_complement
    };
}

async function generateContent(messages) {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        headers: {
            "Authorization": `Bearer ${process.env.OPENROUTER_API_KEY}`,
            "X-Title": `Clippy`,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            model,
            temperature: 1,
            messages,
        })
    });
    const textData = await response.text();
    console.log(textData);
    const jsonData = JSON.parse(textData);
    // const jsonData = await response.json();
    console.log(JSON.stringify(jsonData));
    const content = jsonData.choices[0].message?.content;

    // remove any trailing text in the format of <|xyz|>
    if (content) {
        return content.replace(/<\|.*\|>$/, '');
    }

    return content;
}

function convertHtmlToMarkdown(htmlString) {
    // Create an instance of NodeHtmlMarkdown
    const nhm = new NodeHtmlMarkdown();

    // Convert the HTML string to Markdown
    let markdown = nhm.translate(htmlString);

    // Workaround for tags with alt text starting and ending with a colon
    markdown = markdown.replace(/!\[(.*?)\]\((.*?)\)/g, (match, altText) => {
        if (altText.startsWith(":") && altText.endsWith(":")) {
            return altText;
        }
        return match;
    });

    return markdown;
}

/**
 * Plugin generation function.
 *
 * Returns a plugin object bound to the provided forum provider
 *
 * @param {Provider} forum Active forum Provider
 * @param {object|Array} config Plugin configuration
 * @returns {Plugin} An instance of the Summoner plugin
 */
module.exports = function clippy(forum, config) {


    function count_chars(messages) {
        let total_chars = 0;
        for (const m of messages) {
            total_chars += m.content.length;
        }
        return total_chars;
    }

    function limit_chars(messages, limit) {
        // remove messages from the beginning until the total length is less than the limit or there is less than 5 messages
        while (count_chars(messages) > limit && messages.length > 5) {
            messages.shift();
        }
        return messages;
    }

    /**
     * Handle a mention notification.
     *
     * Choose a random message and reply with it
     *
     * @param {Notification} notification Notification event to handle
     * @returns {Promise} Resolves when event is processed
     */
    async function handler(notification) {
        debug('clippy received a mention notification!');
        try {
            const user = await notification.getUser();
            debug(`clippy responding to ${user.username}`);

            const thepost = await forum.Post.get(notification.postId);
            const topic = await forum.Topic.get(notification.topicId);
            let contextPosts = [];
            await topic.getLatestPosts(async (p) => {
                const postAuthor = await forum.User.get(p.authorId);
                contextPosts.push({ content: p.content, author: postAuthor.username });
            });
            let messages = [];
            for (const p of contextPosts) {
                // name must be ^[a-zA-Z0-9_-]{1,64}$
                let sanitizedName = p.author.replace(/[^a-zA-Z0-9_-]/g, '').substring(0, 64);
                if (sanitizedName.length == 0) {
                    sanitizedName = 'user';
                }
                let role = sanitizedName.toLowerCase().trim() == 'clippy' ? 'assistant' : 'user';
                messages.push({
                    role,
                    name: sanitizedName,
                    content: convertHtmlToMarkdown(p.content)
                });

                // the command !clearcontext clear the context of the conversation
                if (p.content.includes("!clearcontext")) {
                    messages = [];
                }

                // the command !system_message(<new message>) changes the system message
                const system_message_regex = /!system_message ?\((.*)\)/;
                const match = p.content.match(system_message_regex);
                if (match) {
                    system_message = match[1];
                    messages = [];
                }

            }
            messages = limit_chars(messages, character_limit);
            messages.unshift(format_system_message());
            console.log(`System message = ${system_message}`);
            console.log(`Number of context messages: ${contextPosts.length}`);
            console.log(`Post being answered: ${thepost.content}`);
            console.log(`Characters in context: ${count_chars(messages)}`)
            let response = await generateContent(messages);
            console.log(`Response: ${response}`);
            if (!response) {
                return;
            }
            response = surroundMentionsWithColons(response);

            return forum.Post.reply(notification.topicId, notification.postId, response);
        } catch (err) {
            console.log(err)
            forum.emit('error', err);
            return Promise.reject(err);
        };
    }


    /**
     * Activate the plugin
     */
    function activate() {
        forum.on('notification:mention', handler);
    }

    /**
     * Deactivate the plugin
     */
    function deactivate() {
        forum.off('notification:mention', handler);
    }

    return {
        activate: activate,
        deactivate: deactivate,
        handler: handler
    };
};
