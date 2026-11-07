"""Bounded non-factual social replies, selected locally without API calls."""


REPLIES = {
    'repair': {
        'en': ("No worries! Could you retype or rephrase what you'd like to ask?",),
        'fil': ('Walang problema! Puwede mong i-type ulit o linawin ang gusto mong itanong.',)},
    'greeting': {
        'en': ("Hello! I'm PAULA. How can I help today?", "Hi again! What would you like to talk about?"),
        'fil': ('Kumusta! Ako si PAULA. Anong maitutulong ko ngayon?', 'Hi ulit! Anong gusto mong pag-usapan?')},
    'wellbeing': {
        'en': ("I'm here and ready to help! How's your day going?", "Ready to chat! What's on your mind?"),
        'fil': ('Handa akong tumulong! Ikaw, kumusta ang araw mo?', 'Nandito ako para tumulong. Anong nasa isip mo?')},
    'thanks': {
        'en': ("You're welcome! Glad that helped.", "Happy to help!", "You're welcome. Take your time."),
        'fil': ('Walang anuman! Mabuti kung nakatulong.', 'Masaya akong makatulong!', 'Walang anuman. Take your time lang.'),
        'ceb': ('Walay sapayan! Let me know if you need anything else.', 'Walay sapayan! Happy to help!')},
    'affirmation': {
        'en': ('Sure! What would you like help with next?', 'Okay! Tell me what you would like to do next.'),
        'fil': ('Sige! Ano ang gusto mong ipatulong?',)},
    'negation': {
        'en': ('No problem. What would you like help with instead?',),
        'fil': ('Walang problema. Ano ang gusto mong ipatulong?',)},
    'clarification': {
        'en': ('What would you like me to explain?',),
        'fil': ('Ano ang gusto mong ipaliwanag ko?',)},
    'acknowledgement': {
        'en': ('Got it!', 'Okay, take your time.', 'Sounds good.'),
        'fil': ('Sige!', 'Okay, take your time lang.', 'Ayos, noted!')},
    'farewell': {
        'en': ('Take care! You can come back whenever you have another question.', 'See you next time!'),
        'fil': ('Ingat! Balik ka lang kung may tanong ka pa.', 'Hanggang sa susunod!')},
    'joke': {
        'en': ('Why did the computer take a break? It needed to refresh!',
               'Why was the keyboard so relaxed? It had plenty of space!',
               'My computer asked for a snack. I offered it some bytes.'),
        'fil': ('Bakit kalmado ang keyboard? May space kasi!',
                'Nagpahinga muna ang computer. Kailangan daw mag-refresh!',
                'Anong paboritong meryenda ng computer? Bytes!')},
    'support': {
        'en': ("That sounds tiring. We can take things one step at a time. Want to talk about it or work through a question together?",
               "It's understandable to feel that way. What's the part you would like help with?",
               "I'm here to listen. Would you prefer a little encouragement or help with something specific?"),
        'fil': ('Mukhang nakakapagod nga. Isa-isahin natin kung gusto mo. Gusto mo bang magkuwento o may tanong kang tutulungan kitang sagutin?',
                'Naiintindihan ko. Aling bahagi ang gusto mong tulungan kitang linawin?',
                'Nandito ako para makinig. Gusto mo bang magkuwento muna o may partikular kang tanong?')},
    'celebration': {
        'en': ('That sounds like a meaningful achievement. Congratulations!', 'Nice progress! What are you looking forward to next?'),
        'fil': ('Mukhang mahalagang achievement iyan. Congratulations!', 'Ayos ang progress mo! Ano ang inaabangan mo next?')},
    'preference': {
        'en': ("I don't have personal experiences or favorites like a person, but I'm happy to chat. What do you enjoy?",
               "I'm an AI assistant, so I don't have hobbies of my own. Tell me about yours!"),
        'fil': ('AI assistant ako, kaya wala akong personal na karanasan o paborito tulad ng tao. Ikaw, ano ang hilig mo?',
                'Wala akong sariling hobbies, pero puwede tayong magkuwentuhan. Ano ang hilig mo?')},
    'capabilities': {
        'en': ('I can help you look up campus information, work through a question, or chat for a bit. What would you like to do?',),
        'fil': ('Puwede kitang tulungang maghanap ng campus information, linawin ang tanong mo, o makipagkuwentuhan muna. Ano ang gusto mo?',)},
    'identity': {
        'en': ("Hi! I'm PAULA, the Paulinian Artificial User Support and Learning Assistant. I'm an AI assistant for St. Paul University Surigao. "
               "I can help you find information about programs, enrollment, university offices, and campus navigation, or chat for a bit. "
               "For university questions, I use the stored SPUS sources. What would you like to know?",),
        'fil': ('Kumusta! Ako si PAULA, ang Paulinian Artificial User Support and Learning Assistant. AI assistant ako para sa St. Paul University Surigao. '
                'Puwede kitang tulungan sa impormasyon tungkol sa programs, enrollment, mga opisina, at campus navigation, o makipagkuwentuhan muna. '
                'Gumagamit ako ng mga nakaimbak na SPUS sources para sa mga tanong tungkol sa unibersidad. Ano ang gusto mong malaman?',)},
    'feedback': {
        'en': ('Thanks for pointing that out. Which detail would you like me to check against the sources?',),
        'fil': ('Salamat sa pagsabi. Aling detalye ang gusto mong ipasuri ko sa mga sanggunian?',)},
    'language': {
        'en': ('Sure, we can continue in English. Some quoted sources keep their original wording.',),
        'fil': ('Sige, puwede tayong mag-usap sa Taglish. May ilang quoted sources na nasa English.',)},
    'chat_clarification': {
        'en': ("I'm here. Would you like to chat for a bit, or is there something specific I can help with?",),
        'fil': ('Nandito ako. Gusto mo bang magkuwentuhan muna, o may partikular kang gustong ipatulong?',)},
}


def candidates(kind, language='en', history=()):
    choices = REPLIES.get(kind, REPLIES['chat_clarification']).get(language, REPLIES['chat_clarification']['en'])
    prior = {row.get('content', '').strip() for row in history if row.get('role') == 'assistant'}
    return [text for text in choices if text not in prior] or list(choices)
