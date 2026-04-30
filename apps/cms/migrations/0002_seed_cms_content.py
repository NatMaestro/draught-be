from datetime import datetime, timezone as dt_timezone

from django.db import migrations


def seed_cms(apps, schema_editor):
    BlogPost = apps.get_model("cms", "BlogPost")
    FaqItem = apps.get_model("cms", "FaqItem")

    def dt(y, m, d):
        return datetime(y, m, d, 12, 0, tzinfo=dt_timezone.utc)

    if not BlogPost.objects.exists():
        posts = [
            {
                "slug": "why-international-draughts",
                "title": "Why international draughts hooks you (and stays with you)",
                "excerpt": (
                    "Quiet depth, tense endgames, and one clean rule-set — here is why "
                    "polished draught apps keep players coming back."
                ),
                "body": (
                    "International draughts strips away noise. The board looks simple, yet "
                    "every diagonal opens long-term stakes: tempo, structures, and the threat "
                    "of crowned pieces sliding both ways.\n\n"
                    "What keeps matches exciting is how quickly the mood flips. A calm opening "
                    "can collapse into a forced sequence; a single slip hands your opponent a "
                    "tempo that never comes back. That emotional arc is why short sessions feel "
                    "satisfying — and why rematches feel fair.\n\n"
                    "When the experience is smooth — instant moves, respectful timers, readable "
                    "pieces — your brain spends energy on tactics, not on fighting the UI. That "
                    "is the bar we chase with Draught: play first, friction never.\n\n"
                    "If you are new, start with pass & play or a gentle AI level. Patterns stick "
                    "faster when you can experiment without queue anxiety. When you are ready, "
                    "online games add the human unpredictability that makes every match a story."
                ),
                "featured": True,
                "read_time_label": "5 min read",
                "published_at": dt(2026, 3, 2),
            },
            {
                "slug": "install-on-your-phone",
                "title": "Install Draught on your phone (add to home screen)",
                "excerpt": (
                    "Get the game one tap away: install prompts on Android/Chrome, and how to "
                    "add to Home Screen on iPhone and iPad."
                ),
                "body": (
                    "You do not need an app store download to play like a native app. Modern "
                    "browsers can pin Draught to your home screen so it opens full screen, feels "
                    "fast, and stays a tap away.\n\n"
                    "On many Android phones with Chrome, you will see an Install or Add to Home "
                    "screen option after you open the game. Accept it once and the icon sits next "
                    "to your other games.\n\n"
                    "On iPhone or iPad, open the game in Safari, tap the Share button, then Add "
                    "to Home Screen. Name it Draught and confirm. Launch from the icon for a "
                    "standalone, distraction-light experience.\n\n"
                    "Installing also helps if you jump between quick games during the day — the "
                    "shortcut beats hunting through tabs. Pair it with notifications only if we "
                    "add them later; until then, your home-screen icon is the clean signal to "
                    "play one more crisp game."
                ),
                "featured": False,
                "read_time_label": "3 min read",
                "published_at": dt(2026, 3, 18),
            },
            {
                "slug": "three-habits-better-draught",
                "title": "Three habits that sharpen your draught instincts",
                "excerpt": (
                    "Small drills that transfer from puzzles to live games — structure, forcing "
                    "moves, and clock discipline."
                ),
                "body": (
                    "First: treat the long diagonal as scaffolding, not decoration. Pieces that "
                    "grip the longest lanes trade more favors over time — especially once kings "
                    "enter and slide through both colors.\n\n"
                    "Second: scan for forcing replies before you fall in love with a quiet move. "
                    "In draughts, sequences often appear as chains; if you spot the start of a "
                    "compulsion, you either clinch material or steer it somewhere safe.\n\n"
                    "Third: respect the clock even in casual games. Ten-second decisions build "
                    "pattern recognition; longer thinks are for when the position truly "
                    "branches. Carry that mindset online and panic blunders quietly disappear.\n\n"
                    "Bonus habit: replay one messy loss without engine help. Narrate where the "
                    "tension peaked; you learn faster than burning through fresh openings alone."
                ),
                "featured": False,
                "read_time_label": "4 min read",
                "published_at": dt(2026, 4, 8),
            },
        ]

        for row in posts:
            BlogPost.objects.create(
                slug=row["slug"],
                title=row["title"],
                excerpt=row["excerpt"],
                body=row["body"],
                featured=row["featured"],
                published=True,
                published_at=row["published_at"],
                read_time_label=row["read_time_label"],
            )

    if not FaqItem.objects.exists():
        faqs = [
            (
                0,
                "Is Draught free to play?",
                "We aim for a generous free tier so anyone can compete and practice. "
                "Monetization experiments (never pay-to-win) may arrive later.",
            ),
            (
                1,
                "Do I need an account?",
                "You can jump in quickly for many flows. Persistent identity and certain online "
                "features may ask you to register over time.",
            ),
            (
                2,
                "How do installs work on phones?",
                "Supported browsers offer “Install app” or “Add to Home Screen.” iOS prefers "
                "Safari → Share → Add to Home Screen.",
            ),
            (
                3,
                "What ruleset is this?",
                "International draughts (10×10) — crowned pieces slide both ways.",
            ),
            (
                4,
                "Can I play offline?",
                "AI and pass & play can work offline once caching is fully wired in the game’s "
                "PWA. Online modes need a connection.",
            ),
            (
                5,
                "Ads on this site?",
                "The blog supports optional Google AdSense slots. You can manage consent and "
                "learn more on our Privacy page.",
            ),
        ]
        for order, q, a in faqs:
            FaqItem.objects.create(question=q, answer=a, sort_order=order, published=True)


def unseed_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_cms, unseed_noop),
    ]
