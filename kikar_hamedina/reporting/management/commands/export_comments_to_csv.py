#!encoding utf-8
from csv import DictWriter

import json

import dateutil
from django.utils import timezone

from facebook_feeds.models import Facebook_Feed
from facebook_feeds.management.commands.kikar_base_commands import KikarCommentCommand
from reporting.utils import TextProcessor

from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from functools32 import lru_cache

DELIMITER = '~'
PARAGRAPH_LEN_THRESHOLD = 0


class Command(KikarCommentCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('--translate',
                            action='store_true',
                            dest='translate',
                            default=False,
                            help="translate comment data"
                            )
        parser.add_argument('--second_stage',
                            action='store_true',
                            dest='second_stage',
                            default=False,
                            help="if flagged, get second stage features. Otherwise, get first stage."
                            )

    def handle(self, *args, **options):
        print('Start.')

        comments = self.parse_comments(options)
        file_name = '{}_full_data.csv'.format(options['file_path'].split('.csv')[0])
        if options['second_stage']:
            file_name = ''.join([file_name.split('.')[0], '_2nd_stage.', file_name.split('.')[1]])
        f = open(file_name, 'wb')
        if options['second_stage']:
            field_names = [
                'comment_id',
                'MK_ID',
                'mk_name',
                'parent_status_id',
                'parent_status_content',
                'parent_status_link',
                'comment_link',
                'content',
                'content_processed',
                'published',
                'comment_like_count',
                'comment_comment_count',
                'language',
                'LEN_MESSAGE',
                'COMMENTATOR_LIKED_POST',
                'HAS_NAME_OF_POST_WRITER_MK_IN_COMMENT',
                'NON_POST_WRITER_MK_IDS_IN_COMMENT',
                'NUM_OF_COMMENTS_BY_COMMENTATOR_ON_POST',
                'COMMENTATOR_ID',
                'POLITICAL_WING',
                'PARTY_NAME',
                'GENDER',
                'AGE',
                'MK_POLITICAL_STATUS',
                'MK_POLITICAL_SENIORITY',
                'IS_CURRENT_OR_PAST_PARTY_LEADER',
                'IS_CURRENT_OR_PAST_PM_CONTENDER',
                'IS_PM',
                'POST_TIME_OF_PUBLICATION',
                'POST_WITH_PHOTO',
                'POST_WITH_LINK',
                'POST_WITH_VIDEO',
                'POST_WITH_STATUS',
                'POST_WITH_TEXT_ONLY',
                'POST_IN_HEBREW',
                'POST_IN_ENGLISH',
                'POST_IN_ARABIC',
                'POST_IN_OTHER',
                'DAYS_FROM_ELECTION',
                'DAYS_FROM_THREE_TEENAGER_KIDNAP',
                'DAYS_FROM_PROTECTIVE_EDGE_OFFICIAL_START_DATE',
                'DAYS_FROM_PROTECTIVE_EDGE_OFFICIAL_END_DATE',
                'DAYS_FROM_THIRD_INTIFADA_START_DATE',
                'POST_PUBLISHED_ON_SATURDAY',
                'COMMENT_PUBLISHED_ON_SATURDAY',
                'NUM_OF_COMMENTS_BY_COMMENTATOR_ID_ON_GIVEN_MK_POSTS',
                'NUM_OF_LIKES_BY_COMMENTATOR_ID_ON_GIVEN_MK_POSTS',
                'RATIO_OF_COMMENTS_BY_COMMENTATOR_ID_ON_GIVEN_MK_POSTS',
                'RATIO_OF_LIKES_BY_COMMENTATOR_ID_ON_GIVEN_MK_POSTS',

            ]

        else:
            field_names = [
                'comment_id',
                'mk_id',
                'mk_name',
                'parent_status_id',
                'parent_status_content',
                'parent_status_link',
                'comment_link',
                'content',
                'content_processed',
                'published',
                'commentator_id',
                'commentator_also_liked_status',
                'like_count',
                'comment_count',
                'language',
            ]
        csv_data = DictWriter(f, fieldnames=field_names, delimiter=DELIMITER)
        headers = {field_name: field_name for field_name in field_names}
        csv_data.writerow(headers)

        processor = TextProcessor()

        for i, comment in enumerate(comments):
            processed_text = processor.replace_mk_names(text=comment.content, context_status=comment.parent)
            if options['translate']:
                processed_text = processor.request_translated_text_from_google(text=processed_text)
            processed_text = processor.replace_emojis_to_named_text(text=processed_text)
            print('writing comment {} of {}'.format(i + 1, comments.count()))
            if options['second_stage']:
                dict_row = self.get_second_stage_comment_features(comment, processed_text, processor)
            else:
                dict_row = self.get_first_stage_comment_features(comment, processed_text, processor)
            csv_data.writerow(dict_row)

        f.close()
        print('Done.')

    def get_first_stage_comment_features(self, comment, processed_text, processor):
        return {
            'comment_id': comment.comment_id,
            'mk_id': comment.parent.feed.persona.content_object.id,
            'mk_name': processor.flatten_text(comment.parent.feed.persona.content_object.name,
                                              delimiter=DELIMITER),
            'parent_status_id': comment.parent.status_id,
            'parent_status_content': processor.flatten_text(comment.parent.content,
                                                            delimiter=DELIMITER),
            'parent_status_link': comment.parent.get_link,
            'comment_link': 'www.facebook.com/{}'.format(comment.comment_id),
            'content': processor.flatten_text(comment.content, delimiter=DELIMITER),
            'content_processed': processor.flatten_text(processed_text, delimiter=DELIMITER),
            'published': comment.published,
            'commentator_id': comment.comment_from.facebook_id,
            'commentator_also_liked_status': comment.comment_from.likes.filter(
                status__status_id=comment.parent.status_id).exists(),
            'like_count': comment.like_count,
            'comment_count': comment.comment_count,
            'language': comment.content_lang()
        }

    def get_second_stage_comment_features(self, comment, processed_text, processor):
        mk = comment.parent.feed.persona.content_object

        status_langs = self.detect_languages(comment.parent)

        if mk:
            return {
                'comment_id': comment.comment_id,
                'MK_ID': mk.id,
                'mk_name': processor.flatten_text(mk.name,
                                                  delimiter=DELIMITER),
                'parent_status_id': comment.parent.status_id,
                'parent_status_content': processor.flatten_text(comment.parent.content,
                                                                delimiter=DELIMITER),
                'parent_status_link': comment.parent.get_link,
                'comment_link': 'www.facebook.com/{}'.format(comment.comment_id),
                'content': processor.flatten_text(comment.content, delimiter=DELIMITER),
                'content_processed': processor.flatten_text(processed_text, delimiter=DELIMITER),
                'published': comment.published,
                'comment_like_count': comment.like_count,
                'comment_comment_count': comment.comment_count,
                'language': comment.content_lang(),
                'LEN_MESSAGE': len(comment.content),
                'COMMENTATOR_LIKED_POST': comment.comment_from.likes.filter(
                    status__status_id=comment.parent.status_id).exists(),
                'HAS_NAME_OF_POST_WRITER_MK_IN_COMMENT': processor.is_mk_id_pattern_in_text(text=comment.content,
                                                                                            mk_id=mk.id),
                'NON_POST_WRITER_MK_IDS_IN_COMMENT': processor.get_mentioned_mks(text=comment.content),
                'NUM_OF_COMMENTS_BY_COMMENTATOR_ON_POST': self.number_of_comments_by_commentator_on_statuses(
                    comment.comment_from, [comment.parent]),
                'COMMENTATOR_ID': comment.comment_from.facebook_id,
                'POLITICAL_WING': self.get_political_wing(mk.current_party),
                'PARTY_NAME': processor.flatten_text(mk.current_party.name),
                'GENDER': processor.flatten_text(mk.gender),
                'AGE': mk.age.years,
                'MK_POLITICAL_STATUS': None,
                'MK_POLITICAL_SENIORITY': None,
                'IS_CURRENT_OR_PAST_PARTY_LEADER': self.is_current_or_past_party_leader(comment.parent.feed),
                'IS_CURRENT_OR_PAST_PM_CONTENDER': self.is_current_or_past_pm_contender(comment.parent.feed),
                'IS_PM': self.is_pm(comment.parent.feed),
                'POST_TIME_OF_PUBLICATION': comment.parent.published,
                'POST_WITH_PHOTO': comment.parent.has_attachment and comment.parent.attachment.type == 'photo',
                'POST_WITH_LINK': comment.parent.has_attachment and comment.parent.attachment.type == 'link',
                'POST_WITH_VIDEO': comment.parent.has_attachment and comment.parent.attachment.type == 'video',
                'POST_WITH_STATUS': comment.parent.has_attachment and comment.parent.attachment.type == 'status',
                'POST_WITH_TEXT_ONLY': not comment.parent.has_attachment,
                'POST_IN_HEBREW': 'he' in status_langs,
                'POST_IN_ENGLISH': 'en' in status_langs,
                'POST_IN_ARABIC': 'ar' in status_langs,
                'POST_IN_OTHER': bool([x for x in status_langs if x not in ['he', 'en', 'ar']]),
                'DAYS_FROM_ELECTION': self.days_from_event(
                    comment.parent.published, timezone.make_aware(timezone.datetime(2015, 3, 17))),
                'DAYS_FROM_THREE_TEENAGER_KIDNAP': self.days_from_event(
                    comment.parent.published, timezone.make_aware(timezone.datetime(2014, 6, 12))),
                'DAYS_FROM_PROTECTIVE_EDGE_OFFICIAL_START_DATE': self.days_from_event(
                    comment.parent.published, timezone.make_aware(timezone.datetime(2015, 7, 8))),
                'DAYS_FROM_PROTECTIVE_EDGE_OFFICIAL_END_DATE': self.days_from_event(
                    comment.parent.published, timezone.make_aware(timezone.datetime(2015, 8, 26))),
                'DAYS_FROM_THIRD_INTIFADA_START_DATE': self.days_from_event(
                    comment.parent.published, timezone.make_aware(timezone.datetime(2015, 9, 13))),
                'POST_PUBLISHED_ON_SATURDAY': self.is_date_in_holiday(comment.parent.published),
                'COMMENT_PUBLISHED_ON_SATURDAY': self.is_date_in_holiday(comment.published),
                'NUM_OF_COMMENTS_BY_COMMENTATOR_ID_ON_GIVEN_MK_POSTS':
                    self.number_of_comments_by_commentator_for_feed_id(
                        comment.comment_from, comment.parent.feed.id),
                'NUM_OF_LIKES_BY_COMMENTATOR_ID_ON_GIVEN_MK_POSTS':
                    self.num_of_likes_by_commentator_for_feed_id(
                        comment.comment_from, comment.parent.feed.id),
                'RATIO_OF_COMMENTS_BY_COMMENTATOR_ID_ON_GIVEN_MK_POSTS':
                    self.ratio_of_commented_statuses_by_commentator_for_feed_id(comment.comment_from,
                                                                                comment.parent.feed.id),
                'RATIO_OF_LIKES_BY_COMMENTATOR_ID_ON_GIVEN_MK_POSTS':
                    self.ratio_of_likes_by_commentator_on_statuses_by_feed_id(comment.comment_from,
                                                                              comment.parent.feed.id)
            }

    def ratio_of_commented_statuses_by_commentator_for_feed_id(self, commentator, feed_id):
        statuses = Facebook_Feed.objects.get(id=feed_id).facebook_status_set.all()
        return self.number_of_commented_on_statuses_for_feed_id(commentator, feed_id) * 1.0 / statuses.count()

    @lru_cache(maxsize=180)
    def number_of_commented_on_statuses_for_feed_id(self, commentator, feed_id):
        statuses = Facebook_Feed.objects.get(id=feed_id).facebook_status_set.all()
        count_statuses = 0
        for status in statuses:
            count_statuses += int(self.is_status_commented_on_by_commentator(commentator, status))
        return count_statuses

    @lru_cache(maxsize=180)
    def is_status_commented_on_by_commentator(self, commentator, status):
        return commentator.comments.filter(parent__status_id=status.status_id).exists()

    @lru_cache(maxsize=180)
    def number_of_comments_by_commentator_for_feed_id(self, commentator, feed_id):
        statuses = Facebook_Feed.objects.get(id=feed_id).facebook_status_set.all()
        return self.number_of_comments_by_commentator_on_statuses(commentator, statuses)

    def number_of_comments_by_commentator_on_statuses(self, commentator, statuses):
        return commentator.comments.filter(parent__in=statuses).count()

    @lru_cache(maxsize=180)
    def get_number_of_comments_for_feed(self, feed_id):
        feed = Facebook_Feed.objects.get(id=feed_id)
        return self.get_number_of_comments(feed.facebook_status_set.all())

    def get_number_of_comments(self, statuses):
        num_of_comments = 0
        for status in statuses:
            num_of_comments += status.comments.count()
        return num_of_comments

    def ratio_of_likes_by_commentator_on_statuses_by_feed_id(self, commentator, feed_id):
        statuses = Facebook_Feed.objects.get(id=feed_id).facebook_status_set.all()
        return self.num_of_likes_by_commentator_for_feed_id(commentator, feed_id) * 1.0 / statuses.count()

    @lru_cache(maxsize=180)
    def num_of_likes_by_commentator_for_feed_id(self, commentator, feed_id):
        statuses = Facebook_Feed.objects.get(id=feed_id).facebook_status_set.all()
        return self.number_of_likes_by_commentator_on_statuses(commentator, statuses)

    def number_of_likes_by_commentator_on_statuses(self, commentator, statuses):
        return commentator.likes.filter(status__in=statuses).count()

    def get_political_wing(self, party):
        if party.id in [30, 31, 27, 14, 17]:  # Habait Hayehudi, Israel-Beitenu, Likud, Likud-Israel Beitenu
            return 'RIGHT'
        elif party.id in [32, 15, 21, 25, 29]:  # Yesh Atid, Kulanu, Kadima, Hatnua
            return 'CENTER'
        elif party.id in [33, 16, 20, 28]:  # Meretz, Haavoda
            return 'LEFT'
        elif party.id in [35, 10, 22]:  # Joint List and subsidiary
            return 'ARAB'
        elif party.id in [34, 36, 18, 19]:  # Shas, Yehadut Hatora
            return 'CHAREDI'
        else:
            return None

    def days_from_event(self, pub_date, event_date):
        return (pub_date - event_date).days

    def detect_languages(self, status):
        languages = list()
        for paragraph in self.split_text_to_paragraphs(status.content):
            self.remove_stoppharses_from_text(paragraph)
            if len(paragraph) > PARAGRAPH_LEN_THRESHOLD:  # Ignore short
                languages.append(self.detect_language(paragraph))
        return list(set(languages))

    def remove_stoppharses_from_text(self, text):
        stop_phrases = []
        for phrase in stop_phrases:
            text = text.replace(phrase, '')
        return text

    def detect_language(self, text):
        try:
            return detect(text)
        except LangDetectException as e:
            return u''

    def split_text_to_paragraphs(self, text):
        return [text]

    def is_pm(self, feed):
        if feed.id == 30:
            return True
        return False

    def is_current_or_past_pm_contender(self, feed):
        if feed.id in [14, 12, 51, 4]:  # Lapid, Hertzog, Yechimovich, Livni
            return True
        return False

    def is_current_or_past_party_leader(self, feed):
        if feed.id in [53, 109, 141, 138, 4, 52, 80, 20, 51, 40, 79, 54, 14, 35, 30, 73, 12, 22, 89, 44]:
            return True
        return False

    def is_date_in_holiday(self, pub_date):
        time_pairs = self.load_shabbat_time_pairs()
        for pair in time_pairs:
            if pair[0] <= pub_date <= pair[1]:
                return True
        return False

    def load_shabbat_time_pairs(self):
        with open('time_pairs.json', 'r') as f:
            time_pairs = json.load(f)
        parsed_time_pairs = []
        for pair in time_pairs:
            parsed_time_pairs.append((dateutil.parser.parse(pair[0]), dateutil.parser.parse(pair[1])))
        return parsed_time_pairs
