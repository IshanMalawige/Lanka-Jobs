from datetime import datetime
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Job, Status
from app.routers.jobs import count_jobs, list_jobs, refresh_one_job_details, update_job
from app.scrapers.base import RawJob
from app.scrapers.runner import save_raw_jobs
from app.schemas import JobUpdate


class JobSortTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_match_sort_ranks_before_pagination_and_puts_missing_scores_last(self):
        self.session.add_all([
            Job(title="Python role", category="IT", source="itpro", url="https://example.com/python", description="Python"),
            Job(title="Python and SQL role", category="IT", source="itpro", url="https://example.com/python-sql", description="Python SQL"),
            Job(title="General role", category="IT", source="itpro", url="https://example.com/general", description="General role"),
        ])
        self.session.commit()

        with patch("app.routers.jobs.get_profile", return_value={"skills": ["python"]}):
            first_page = list_jobs(sort="match", limit=2, offset=0, db=self.session)
            second_page = list_jobs(sort="match", limit=2, offset=2, db=self.session)

        self.assertEqual(
            [job["title"] for job in first_page],
            ["Python role", "Python and SQL role"],
        )
        self.assertEqual([job["skill_match"]["match_percent"] for job in first_page], [100, 50])
        self.assertEqual([job["title"] for job in second_page], ["General role"])
        self.assertIsNone(second_page[0]["skill_match"]["match_percent"])

    def test_job_can_be_marked_viewed(self):
        job = Job(
            title="IT Support role",
            category="IT",
            source="itpro",
            url="https://example.com/it-support",
        )
        self.session.add(job)
        self.session.commit()

        updated = update_job(job.id, JobUpdate(status=Status.viewed), db=self.session)

        self.assertEqual(updated.status, Status.viewed)

    def test_position_and_experience_filters_apply_before_pagination(self):
        self.session.add_all([
            Job(
                title="Junior IT Support Engineer",
                category="IT Support",
                source="itpro",
                url="https://example.com/junior-two-years",
                description="Requires 2 years of experience.",
            ),
            Job(
                title="Senior Network Engineer",
                category="Network",
                source="itpro",
                url="https://example.com/senior-five-years",
                description="Requires 5 years of experience.",
            ),
            Job(
                title="Junior Systems Engineer",
                category="Systems",
                source="itpro",
                url="https://example.com/junior-unspecified",
            ),
        ])
        self.session.commit()

        jobs = list_jobs(
            level="junior",
            experience="2-3",
            limit=1,
            offset=0,
            include_match=False,
            db=self.session,
        )

        self.assertEqual([job.title for job in jobs], ["Junior IT Support Engineer"])

    def test_job_count_applies_filters_and_excludes_bank_career_records(self):
        self.session.add_all([
            Job(
                title="Junior IT Support Engineer",
                category="IT Support",
                source="itpro",
                url="https://example.com/junior-it-support",
                description="Requires 2 years of experience.",
            ),
            Job(
                title="Senior IT Support Engineer",
                category="IT Support",
                source="itpro",
                url="https://example.com/senior-it-support",
                description="Requires 5 years of experience.",
            ),
            Job(
                title="Junior IT Support Engineer",
                category="IT Support",
                source="careers",
                url="https://example.com/bank-career",
            ),
            Job(
                title="Junior Systems Engineer",
                category="Systems",
                source="itpro",
                url="https://example.com/junior-systems",
            ),
        ])
        self.session.commit()

        result = count_jobs(
            category="IT Support",
            source="itpro",
            level="junior",
            experience="2-3",
            db=self.session,
        )

        self.assertEqual(result, {"total": 1})

    def test_interns_filter_includes_legacy_internship_categories(self):
        job = Job(
            title="Python Internship",
            category="Internship",
            source="itpro",
            url="https://example.com/vacancy/1/internship",
        )
        self.session.add(job)
        self.session.commit()

        jobs = list_jobs(
            category="Interns",
            limit=300,
            offset=0,
            include_match=False,
            db=self.session,
        )

        self.assertEqual([item.title for item in jobs], [job.title])

    def test_all_sources_excludes_bank_career_site_jobs(self):
        self.session.add_all([
            Job(
                title="Be a part of an award winning dynamic team",
                company="Amana Bank",
                category="Banking",
                source="careers",
                url="https://www.amanabank.lk/cdn-cgi/l/email-protection#1234",
            ),
            Job(
                title="Current Vacancies",
                company="Amana Bank",
                category="Banking",
                source="careers",
                url="https://careers.amanabank.lk/",
            ),
            Job(
                title="Python Developer",
                company="Example Co",
                category="IT",
                source="itpro",
                url="https://example.com/python-developer",
            ),
        ])
        self.session.commit()

        jobs = list_jobs(limit=10, offset=0, include_match=False, db=self.session)

        self.assertEqual(
            [job.title for job in jobs],
            ["Python Developer"],
        )

    def test_refresh_replaces_topjobs_placeholder_and_brand_logo(self):
        job = Job(
            title="IT Support role",
            category="IT",
            source="topjobs",
            url="https://www.topjobs.lk/employer/JobAdvertismentServlet?jc=123",
            description="Please refer the full details of the job posting as given by the employer.",
            how_to_apply="See the original job posting for the employer's application instructions.",
            poster_image_url="https://topjobs.lk/images/public/tj.jpg",
        )
        self.session.add(job)
        self.session.commit()

        with patch(
            "app.services.job_details.fetch_job_details",
            return_value={
                "description": "The employer did not provide a detailed description. Closing date: 15/01/2027.",
                "requirements": "",
                "how_to_apply": "Send your CV to: hr@example.com",
                "poster_image_url": "",
            },
        ):
            updated = refresh_one_job_details(job.id, db=self.session)

        self.assertIn("Closing date", updated.description)
        self.assertEqual(updated.how_to_apply, "Send your CV to: hr@example.com")
        self.assertEqual(updated.poster_image_url, "")
        self.assertIsNotNone(updated.details_fetched_at)

    def test_refresh_replaces_generic_topjobs_description_with_poster_text(self):
        job = Job(
            title="Junior IT Support Executive",
            company="Aimpos (Pvt) Ltd",
            category="IT Support",
            source="topjobs",
            url="https://www.topjobs.lk/employer/JobAdvertismentServlet?jc=123",
            description="The employer did not provide a detailed description. Available listing details: Colombo.",
            how_to_apply="Apply through TopJobs using your online CV.",
            poster_image_url="https://www.topjobs.lk/logo/DEFZZZ/1810c1006.png",
            details_fetched_at=datetime(2026, 11, 1),
        )
        self.session.add(job)
        self.session.commit()

        with patch(
            "app.services.job_details.fetch_job_details",
            return_value={
                "description": "Junior IT Support Executive\nSupport UK clients.",
                "requirements": "",
                "how_to_apply": "Send your CV to: aimposjobs@gmail.com",
                "poster_image_url": job.poster_image_url,
            },
        ):
            updated = refresh_one_job_details(job.id, force=True, db=self.session)

        self.assertIn("Support UK clients", updated.description)
        self.assertEqual(updated.how_to_apply, "Send your CV to: aimposjobs@gmail.com")

    def test_new_topjobs_placeholder_is_enriched_immediately(self):
        raw_job = RawJob(
            title="Junior IT Support Executive",
            company="Aimpos (Pvt) Ltd",
            url="https://www.topjobs.lk/employer/JobAdvertismentServlet?jc=456",
            source="topjobs",
            description="Please refer the full details of the job posting as given by the employer.",
        )

        with (
            patch("app.scrapers.runner._enrich_job") as enrich,
            patch("app.scrapers.runner.queue_high_match_job"),
        ):
            added = save_raw_jobs(self.session, [raw_job])

        job = self.session.query(Job).filter_by(url=raw_job.url).one()
        self.assertEqual(added, 1)
        enrich.assert_called_once_with(self.session, job)

    def test_existing_topjobs_placeholder_is_not_reenriched_after_a_fetch_attempt(self):
        raw_job = RawJob(
            title="Junior IT Support Executive",
            company="Aimpos (Pvt) Ltd",
            url="https://www.topjobs.lk/employer/JobAdvertismentServlet?jc=789",
            source="topjobs",
            description="Please refer the full details of the job posting as given by the employer.",
        )
        self.session.add(Job(
            title=raw_job.title,
            company=raw_job.company,
            category="IT Support",
            source=raw_job.source,
            url=raw_job.url,
            description=raw_job.description,
            details_fetched_at=datetime(2026, 11, 1),
        ))
        self.session.commit()

        with patch("app.scrapers.runner._enrich_job") as enrich:
            added = save_raw_jobs(self.session, [raw_job])

        self.assertEqual(added, 0)
        enrich.assert_not_called()

    def test_refresh_can_fetch_missing_poster_image_for_cached_details(self):
        job = Job(
            title="IT Support role",
            category="IT",
            source="itpro",
            url="https://itpro.lk/jobs/it-support",
            description="Existing job description.",
            details_fetched_at=datetime(2026, 11, 1),
        )
        self.session.add(job)
        self.session.commit()

        with patch(
            "app.services.job_details.fetch_job_details",
            return_value={
                "description": "Updated description that should not replace the saved text.",
                "requirements": "",
                "how_to_apply": "",
                "poster_image_url": "https://itpro.lk/images/it-support-poster.jpg",
            },
        ) as fetch_details:
            updated = refresh_one_job_details(job.id, force=True, db=self.session)

        fetch_details.assert_called_once_with(job.url, job.source)
        self.assertEqual(updated.description, "Existing job description.")
        self.assertEqual(updated.poster_image_url, "https://itpro.lk/images/it-support-poster.jpg")


if __name__ == "__main__":
    unittest.main()
