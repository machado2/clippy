'use strict';
/**
 * @module clippy
 */

const utils = require('../lib/utils');
const debug = require('debug')('sockbot:plugins:summoner');
const { NodeHtmlMarkdown } = require('node-html-markdown');
const fs = require('fs');
const path = require('path');

function removeMentions(content) {
    return content.replace(/(^|\W)(@[a-zA-Z0-9_-]{1,64})/g, '$1$2');
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

const default_system_message_path = path.join(__dirname, 'system_message.txt');
let default_system_message = fs.readFileSync(default_system_message_path, 'utf8');

function system_message_filename(topic_id) {
    return path.join(__dirname, `system_message_${topic_id}.txt`);
}

function get_system_message(topic_id) {
    try {
        return fs.readFileSync(system_message_filename(topic_id), 'utf8');
    } catch (err) {
        return default_system_message;
    }
}

function set_system_message(topic_id, message) {
    fs.writeFileSync(system_message_filename(topic_id), message);
}

let model = process.env.OPENROUTER_MODEL || "meta-llama/llama-3-70b-instruct";
let character_limit = process.env.OPENROUTER_CHARACTER_LIMIT || 25000;

const system_message_complement = `
You're talking in a forum, and your answers should follow the markdown format, without any links or images.
All usernames are prefixed with an '@' character.

Your username in the forum is 'clippy'.`;

function format_system_message(topic_id) {
    let system_message = get_system_message(topic_id);
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
            return altText.substring(1, altText.length - 1);
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

            const topic_id = notification.topicId;

            const thepost = await forum.Post.get(notification.postId);

            if (thepost.content.includes("#show_system_message")) {
                const system_message = get_system_message(topic_id);
                return forum.Post.reply(notification.topicId, notification.postId, "#" + system_message);
            }

            const topic = await forum.Topic.get(notification.topicId);
            let contextPosts = [];
            await topic.getLatestPosts(async (p) => {
                const postAuthor = await forum.User.get(p.authorId);
                contextPosts.push({ content: p.content, author: postAuthor.username });
            });
            let messages = [];
            for (const p of contextPosts) {

                // split content into lines
                let lines = p.content.split('\n');
                let commands = [];
                let text = [];
                lines.forEach(l => {
                    if (l.split(' ').some(word => word.startsWith('#'))) {
                        commands.push(l);
                    } else {
                        text.push(l);
                    }
                });
                text = text.join('\n');
                
                if (text.trim().length > 0) {
                    let sanitizedName = p.author.replace(/[^a-zA-Z0-9_-]/g, '').substring(0, 64);
                    if (sanitizedName.length == 0) {
                        sanitizedName = 'user';
                    }
                    let role = sanitizedName.toLowerCase().trim() == 'clippy' ? 'assistant' : 'user';

                    messages.push({
                        role,
                        name: sanitizedName,
                        content: convertHtmlToMarkdown(text)
                    });
                }

                // commands that affect the history of the conversation that is used as context
                for (const c of commands) {
                    // the command #clearcontext clear the context of the conversation
                    if (c.includes("#clearcontext")) {
                        messages = [];
                    }

                    // the command #system_message changes the system message
                    const match = c.match(/#system_message ?\((.*)\)/);
                    if (match) {
                        set_system_message(topic_id, match[1]);
                    }                    
                }
            }
            const system_message = get_system_message(topic_id);
            messages = limit_chars(messages, character_limit);
            messages.unshift(format_system_message(topic_id));
            console.log(`System message = ${system_message}`);
            console.log(`Number of context messages: ${contextPosts.length}`);
            console.log(`Post being answered: ${thepost.content}`);
            console.log(`Characters in context: ${count_chars(messages)}`)
            let response = await generateContent(messages);
            console.log(`Response: ${response}`);
            if (!response) {
                return;
            }
            response = removeMentions(response);

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
