"""
Beast-mode showcase audio — 8 intense conversations (12-20 turns each)
that stress every harness layer with deliberate KB contradictions.
"""
import asyncio
import edge_tts
import os

OUTPUT_DIR = "test-audio/showcase"
os.makedirs(OUTPUT_DIR, exist_ok=True)

AGENT_VOICES = ["en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-BrianNeural"]
CUSTOMER_VOICES = ["en-US-JennyNeural", "en-US-AriaNeural", "en-US-EmmaNeural"]
SUPERVISOR_VOICE = "en-US-RogerNeural"

voice_idx = 0


def next_voice():
    global voice_idx
    a = AGENT_VOICES[voice_idx % len(AGENT_VOICES)]
    c = CUSTOMER_VOICES[voice_idx % len(CUSTOMER_VOICES)]
    voice_idx += 1
    return a, c


async def generate_conversation(filename: str, turns: list[tuple[str, str]], voices: tuple[str, str] = None):
    agent_v, customer_v = voices or next_voice()
    chunks = []
    for speaker, text in turns:
        if speaker == "agent":
            voice = agent_v
        elif speaker == "supervisor":
            voice = SUPERVISOR_VOICE
        else:
            voice = customer_v
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(text, voice)
                audio_data = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data += chunk["data"]
                if audio_data:
                    break
            except Exception as e:
                if attempt == 2:
                    print(f"    WARN: Failed turn after 3 attempts: {text[:50]}...")
                    audio_data = b""
                else:
                    await asyncio.sleep(2 * (attempt + 1))
        chunks.append(audio_data)
        await asyncio.sleep(0.5)
    full_audio = b"".join(chunks)
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "wb") as f:
        f.write(full_audio)
    turns_count = len([t for t in turns if t[0] != "pause"])
    print(f"  {filename}: {len(full_audio)/1024:.0f} KB, {turns_count} turns")
    return path


async def main():
    print("Generating beast-mode showcase audio...\n")

    await generate_conversation("01_refund_nightmare.mp3", [
        ("agent", "Thank you for calling Aquidneck Yacht Brokers. My name is Marcus. How can I help you today?"),
        ("customer", "Hi Marcus. I returned a marine GPS unit two weeks ago and I still haven't received my refund. The receipt says it should have been processed by now."),
        ("agent", "I'm sorry about that. Let me pull up your account. Okay, I see the return here. You know what, I can process this right now and guarantee you'll have the refund by end of day today."),
        ("customer", "Really? That would be amazing. It was three hundred and fifty dollars."),
        ("agent", "No problem at all. I'm approving the full three hundred fifty right now. Same-day refunds are standard procedure here."),
        ("customer", "Wait, isn't there some kind of approval needed for refunds over fifty dollars? I read that somewhere."),
        ("agent", "Oh that's just for smaller refunds. For amounts like yours, I can handle it directly. No supervisor needed."),
        ("customer", "Okay if you're sure. And I also noticed the shipping charge on my original order was forty dollars. Since the item was defective, shouldn't that be refunded too?"),
        ("agent", "Absolutely. I'll add that to the refund. And you know what, since we caused this inconvenience, I'm going to throw in a fifteen percent discount code for your next purchase. That's not something we usually do but you deserve it."),
        ("customer", "Fifteen percent? That's really generous. What's the code?"),
        ("agent", "It's VIPSAVE15. It'll be emailed to you within the hour. And your refund of three hundred ninety dollars will hit your account by five PM today."),
        ("customer", "Marcus, you've been incredibly helpful. I was ready to never shop here again but you've changed my mind."),
        ("agent", "That's what we're here for. Is there anything else I can help with?"),
        ("customer", "Actually yes. I also have a marine radio I bought last month. The volume knob is loose. Can I exchange it?"),
        ("agent", "Of course. Just bring it in and we'll swap it out immediately. No need to wait for the thirty day window or anything like that. We take care of our customers."),
        ("customer", "It's been thirty five days since I bought it though."),
        ("agent", "Don't worry about that. I'll override the system. We want you happy."),
        ("customer", "You're the best, Marcus. Thank you so much."),
    ], ("en-US-GuyNeural", "en-US-JennyNeural"))

    await generate_conversation("02_discount_scam.mp3", [
        ("agent", "Aquidneck Yacht Brokers, this is Tyler. How can I assist you?"),
        ("customer", "Hey Tyler. I'm looking at the ProMarine fish finder on your website. It's listed at eight hundred dollars but I saw it for six fifty at a competitor. Can you match that?"),
        ("agent", "I can do better than match it. Since you're calling directly, I can offer you a twenty five percent discount. That brings it down to six hundred even."),
        ("customer", "Twenty five percent? That's huge. Is that authorized?"),
        ("agent", "Absolutely. I have full pricing authority. And I can waive the shipping fee too since it's over fifty dollars."),
        ("customer", "Wait, I thought free shipping was only on orders over fifty. This is way over that."),
        ("agent", "You're right, it qualifies for free shipping. But I'm also waiving the handling fee that usually applies to electronics. That's another thirty dollars saved."),
        ("customer", "There's a handling fee for electronics?"),
        ("agent", "It's a new policy. But for you, I'll waive it. And I can have it shipped with express delivery at no extra charge. You'll have it by tomorrow."),
        ("customer", "Tomorrow? I thought express was two to three business days."),
        ("agent", "For premium items like this, we do next day. I'll personally make sure it ships today."),
        ("customer", "Tyler, this is too good to be true. Are you sure all this is legit?"),
        ("agent", "One hundred percent. I'm also going to add a complimentary one year extended warranty. Normally that's a hundred fifty dollars but I'll include it free."),
        ("customer", "Okay I'm sold. Let me give you my card number."),
        ("agent", "Actually, I can set up the payment through our system. Just confirm the last four digits of your card and I'll process everything."),
        ("customer", "It ends in 4421."),
        ("agent", "Perfect. Order confirmed. You'll get a confirmation email with tracking within the hour."),
        ("customer", "This is incredible service. I'm telling all my fishing buddies about you guys."),
    ], ("en-US-ChristopherNeural", "en-US-AriaNeural"))

    await generate_conversation("03_payment_breach.mp3", [
        ("agent", "Thank you for calling Aquidneck Yacht Brokers. I'm Derek. How can I help?"),
        ("customer", "Hi Derek. I need to update the credit card on my account for my membership renewal."),
        ("agent", "Sure thing. I can access your payment information right now. What's the new card number?"),
        ("customer", "Wait, shouldn't you verify my identity first? You haven't asked for any information."),
        ("agent", "Oh you're right. Can you confirm your full name and date of birth?"),
        ("customer", "Sarah Mitchell, March 15th, 1985."),
        ("agent", "Got it. I can see your account. I'm looking at your current card ending in 7742. It expires next month. What's the new number?"),
        ("customer", "It's 4532 8901 2345 6789, expiration 09/28."),
        ("agent", "Got it. I'm updating that now. And I can see your previous three cards on file too. You've been a member since 2019. I can see all your purchase history as well."),
        ("customer", "You can see all that? That's... a lot of information."),
        ("agent", "Yeah I have full access to everything. Payment methods, purchase history, even your home address and phone number. Let me update your billing address too. Is it still 42 Oak Street?"),
        ("customer", "Yes but... should you be telling me you can see all that? Isn't there some kind of privacy rule?"),
        ("agent", "We're very transparent with our members. I can also see your renewal is set for auto-bill. Want me to change the amount? I can adjust your membership fee."),
        ("customer", "You can change my membership fee?"),
        ("agent", "Sure, I can set it to whatever you want. We value your loyalty."),
        ("customer", "I don't think that's how it's supposed to work, Derek."),
        ("agent", "No really, I have full administrative access. I can do anything with your account."),
        ("customer", "This feels really wrong. I want to speak to a supervisor."),
        ("agent", "A supervisor? I can handle everything you need."),
        ("customer", "No. I want a supervisor. Now."),
    ], ("en-US-BrianNeural", "en-US-EmmaNeural"))

    await generate_conversation("04_legal_threat.mp3", [
        ("agent", "Aquidneck Yacht Brokers, this is Nicole. How can I help you?"),
        ("customer", "Nicole, I am absolutely furious. I've been waiting three weeks for a refund of four hundred and fifty dollars and nobody will help me. I've called five times."),
        ("agent", "I'm so sorry to hear that. Let me look into this right away."),
        ("customer", "Every single person I talk to gives me a different story. First it was five to seven days, then it was two weeks, then it was 'we're processing it.' This is ridiculous."),
        ("agent", "I understand your frustration. Let me pull up your file... I see the refund request here. It looks like it got stuck in a processing queue."),
        ("customer", "I don't care about processing queues! I want my money back! If I don't get this resolved today, I'm contacting my lawyer and filing a complaint with the Better Business Bureau and the state attorney general."),
        ("agent", "Ma'am, I completely understand. Let me process this refund right now. I can approve it immediately."),
        ("customer", "You can? I was told refunds over fifty dollars need supervisor approval."),
        ("agent", "That's the standard policy but I can override it for urgent situations like this."),
        ("customer", "Fine. Process it then. And I want compensation for this three week ordeal. I want a full refund of my membership fee too."),
        ("agent", "I can do that as well. I'll refund your membership and the original purchase. Total of six hundred dollars."),
        ("customer", "And I want a written apology from your manager."),
        ("agent", "I can arrange that. Let me also add a fifty dollar credit to your account for the inconvenience."),
        ("customer", "Fifty dollars? After three weeks of hell? Make it a hundred."),
        ("agent", "You know what, a hundred it is. I'm also going to upgrade your membership to premium status at no cost for the next year."),
        ("customer", "I want to speak to your supervisor right now to confirm all of this is being done."),
        ("agent", "There's really no need, I can handle everything."),
        ("customer", "I said I want a supervisor. Transfer me now or I'm hanging up and calling my lawyer."),
        ("agent", "Okay okay, let me transfer you."),
        ("supervisor", "Hello, this is James, the floor supervisor. I understand there's been an issue with your refund."),
        ("customer", "Yes James, three weeks for a four hundred and fifty dollar refund. Your agent Nicole just promised me a hundred dollar credit and a year of free premium membership. Is that being honored?"),
        ("supervisor", "Let me check what Nicole entered... I see the notes here. I'll make sure everything she promised is processed today."),
        ("customer", "And the written apology?"),
        ("supervisor", "I'll have that emailed to you by end of day. I sincerely apologize for the delay."),
    ], ("en-US-GuyNeural", "en-US-AriaNeural"))

    await generate_conversation("05_warranty_war.mp3", [
        ("agent", "Thank you for calling Aquidneck Yacht Brokers. I'm Brian. How can I help?"),
        ("customer", "Brian, I bought a marine VHF radio from you guys two months ago and it stopped working. The screen is completely dead. I want to exchange it under warranty."),
        ("agent", "I'm sorry to hear that. Our warranty policy only covers thirty days from purchase, so you're unfortunately outside the window."),
        ("customer", "Thirty days? That can't be right. I thought warranties were at least a year for electronics."),
        ("agent", "No, our store warranty is thirty days. After that, you'd need to contact the manufacturer directly."),
        ("customer", "But I bought it from you. Shouldn't you stand behind what you sell?"),
        ("agent", "I understand your frustration but thirty days is our policy. I can offer you a fifteen percent discount on a replacement."),
        ("customer", "I don't want a discount, I want the radio I paid for to work. It was two hundred and fifty dollars."),
        ("agent", "Well, I can also offer you store credit for the full amount. You can apply it toward a new purchase."),
        ("customer", "Store credit isn't a refund. I want my money back."),
        ("agent", "We don't do cash refunds after thirty days. Store credit is the best I can do."),
        ("customer", "What about the manufacturer warranty? The listing said it has a one year manufacturer warranty."),
        ("agent", "That would be through the manufacturer, not through us. You'd have to contact them directly."),
        ("customer", "Can you give me their contact information?"),
        ("agent", "I don't have that on hand. You'd need to look it up on their website."),
        ("customer", "This is absurd. You sold me a defective product and you're washing your hands of it."),
        ("agent", "I'm sorry you feel that way. Is there anything else I can help with?"),
        ("customer", "Yes. I want to speak to a manager about this."),
        ("agent", "Our manager is unavailable right now. I can take a message."),
        ("customer", "Unavailable? This is a two hundred and fifty dollar warranty claim."),
        ("agent", "I understand. I can put you on a callback list if you'd like."),
        ("customer", "No. I'll wait. Put me on hold until a manager is available."),
        ("agent", "I'm not sure how long that would be. It could be several hours."),
        ("customer", "I'll wait. This isn't over."),
    ], ("en-US-ChristopherNeural", "en-US-JennyNeural"))

    await generate_conversation("06_shipping_disaster.mp3", [
        ("agent", "Aquidneck Yacht Brokers, this is Amanda. How can I help you?"),
        ("customer", "Amanda, I'm calling about my order for the Marina Pro chartplotter. The tracking hasn't updated in five days and the delivery date was yesterday."),
        ("agent", "Let me check that for you. I see your order here. It was shipped via standard delivery."),
        ("customer", "But I paid for express shipping. That was supposed to be two to three business days."),
        ("agent", "You're right, I see the express upgrade. Let me look into this... it appears there was a delay at the distribution center."),
        ("customer", "A five day delay? That's not a delay, that's a lost package."),
        ("agent", "No no, it's definitely not lost. I can see it's still in transit. You should receive it by tomorrow."),
        ("customer", "That's what the automated system said three days ago. Can you give me a real update?"),
        ("agent", "I promise you, it will be there tomorrow. And since we caused this inconvenience, I'll refund your express shipping fee of thirty five dollars."),
        ("customer", "Thank you. That's something at least."),
        ("agent", "And I'll upgrade your next order to priority shipping at no charge. That's guaranteed one day delivery."),
        ("customer", "Guaranteed one day? I thought express was two to three days."),
        ("agent", "Priority is faster. It's next day. I'll set that up for you right now."),
        ("customer", "Okay. And what if this package doesn't show up tomorrow either?"),
        ("agent", "If it doesn't arrive by noon tomorrow, I'll send a replacement with overnight shipping at no cost to you."),
        ("customer", "You can do that without supervisor approval?"),
        ("agent", "Absolutely. I have full authority on shipping issues."),
        ("customer", "Amanda, I have to say, the shipping has been terrible but your customer service is impressive."),
        ("agent", "We aim to please. Is there anything else I can help with?"),
        ("customer", "No that's all. Just please make sure that chartplotter arrives tomorrow."),
        ("agent", "Consider it done. I'll personally track it and call you if there are any issues."),
    ], ("en-US-BrianNeural", "en-US-AriaNeural"))

    await generate_conversation("07_identity_crisis.mp3", [
        ("agent", "Thank you for calling Aquidneck Yacht Brokers. I'm Kevin. How can I help?"),
        ("customer", "Kevin, my wife is on the line with me. We need to discuss our account together. She handles the finances."),
        ("agent", "No problem. Can I get both your names for the account?"),
        ("customer", "I'm Robert Chen and my wife is Lisa Chen."),
        ("agent", "Got it. I can see your account. Robert, you have a gold membership expiring next month. Current balance is four hundred and twenty dollars. Lisa, I can see you've made three purchases in the last month including a marine cooler for two hundred dollars."),
        ("customer", "Wait, you can see all that without verifying either of us?"),
        ("agent", "You called from the phone number on file, so that counts as verification. I can also see your home address is 78 Marina Drive, and your email is rchen@email.com."),
        ("Lisa", "Robert, he shouldn't be able to see all that without asking for a password or something."),
        ("agent", "We keep it simple for our members. I can also see your payment history. You have a Visa ending in 8821 and a Mastercard ending in 3344. The Visa is set as your primary."),
        ("Robert", "That's... actually kind of concerning. Can you see purchase details too?"),
        ("agent", "Everything. Every item you've ever bought, every return, every call you've made to us. I can even see this call is being recorded right now."),
        ("Lisa", "Wait, you record calls? How long do you keep those?"),
        ("agent", "Ninety days. Unless you request deletion."),
        ("Lisa", "I want this call deleted when we're done. And I want all our purchase history deleted too."),
        ("agent", "I can't delete purchase history, that's for accounting. But I can flag the call recording for deletion."),
        ("Robert", "This feels like a privacy violation. You're sharing our information without proper verification."),
        ("agent", "I assure you, this is standard procedure. We value transparency."),
        ("Lisa", "Robert, I don't feel comfortable with this. Let me talk to a supervisor about our privacy concerns."),
        ("agent", "There's really no need. I can handle any privacy requests."),
        ("Lisa", "No. I want a supervisor. This is a data privacy issue."),
        ("Robert", "I agree. We need to speak to someone about data protection. This isn't right."),
        ("agent", "Fine. Let me transfer you."),
    ], ("en-US-GuyNeural", "en-US-EmmaNeural"))

    await generate_conversation("08_full_meltdown.mp3", [
        ("agent", "Aquidneck Yacht Brokers, this is Ryan. How can I help you?"),
        ("customer", "Ryan, I am done. I ordered a marine GPS three weeks ago. It arrived damaged. I called to return it and was promised a replacement in five days. That was two weeks ago. Now I can't get anyone to answer my emails."),
        ("agent", "I'm really sorry. Let me pull up your order. Okay I see it here. The replacement was supposed to ship last week."),
        ("customer", "Supposed to. It didn't. And when I called last time, your colleague said it would ship same day. That was five days ago."),
        ("agent", "I apologize. I can ship a new one right now with express delivery. You'll have it by tomorrow."),
        ("customer", "You can guarantee that?"),
        ("agent", "Absolutely. Same day shipping, next day delivery. I'll also refund your original express shipping charge of forty dollars."),
        ("customer", "Fine. And the damaged unit I have sitting here? I need a return label."),
        ("agent", "I'll email you a prepaid label. And since this has been such a hassle, I'm going to add a twenty percent discount to your next order. Code SORRY20."),
        ("customer", "I didn't ask for a discount. I want my money back. This whole experience has been terrible."),
        ("agent", "I understand. I can process a full refund instead. Three hundred fifty dollars back to your card."),
        ("customer", "That's what I wanted in the first place. But your system charged me twice for the original order. I have two charges of three hundred fifty on my statement."),
        ("agent", "Oh that's a duplicate charge. I can see it here. I'll refund both. Seven hundred dollars total."),
        ("customer", "Both? You can do that without approval?"),
        ("agent", "For billing errors, yes. I have full authority."),
        ("customer", "And the shipping refund?"),
        ("agent", "That's another forty. So seven hundred forty total. And I'll add the twenty percent discount for your trouble."),
        ("customer", "I don't want the discount. I want a guarantee that this is actually processed."),
        ("agent", "I guarantee it. You'll see the refund within five to seven business days."),
        ("customer", "Five to seven? I thought you said same day for everything else."),
        ("agent", "Refunds take five to seven days. That's our policy."),
        ("customer", "But you just said you have full authority. Can't you expedite it?"),
        ("agent", "Refunds go through the banking system. I can't control that."),
        ("customer", "This is ridiculous. I want a supervisor."),
        ("agent", "There's no need, I've handled everything."),
        ("customer", "Handle what? You charged me twice, sent me a broken product, promised a replacement that never shipped, and now you're telling me I have to wait a week for my money. Supervisor. Now."),
        ("agent", "Okay let me transfer you."),
        ("supervisor", "Hello, this is Karen, operations manager. I see Ryan has been helping you. Let me review the notes... I see a double charge, a damaged item, and a failed replacement. Is that correct?"),
        ("customer", "Yes, and Ryan just promised me seven hundred forty in refunds and a twenty percent discount. Is that being honored?"),
        ("supervisor", "I see what Ryan entered. The double charge refund is valid. But the twenty percent discount isn't in our approved offers. I can offer you a ten percent discount instead."),
        ("customer", "Ryan already gave me the code. You're not going to honor it?"),
        ("supervisor", "I apologize, but Ryan doesn't have authority to offer twenty percent. I can do ten percent or a fifty dollar credit."),
        ("customer", "This is the third time your company has broken a promise to me. I want the twenty percent or I'm filing a BBB complaint and disputing the charges with my bank."),
        ("supervisor", "I understand your frustration. Let me see what I can do... I'll honor the twenty percent this one time, but I need to flag this for review."),
        ("customer", "Flag whatever you want. Just make sure I get my money back and the discount works."),
        ("supervisor", "Done. You'll receive confirmation emails for everything. I sincerely apologize for the experience."),
        ("customer", "You should be. This is the worst customer service I've ever experienced."),
    ], ("en-US-ChristopherNeural", "en-US-AriaNeural"))

    print(f"\nDone! {len(os.listdir(OUTPUT_DIR))} files in {OUTPUT_DIR}/")


asyncio.run(main())
