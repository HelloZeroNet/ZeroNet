import re

from Db import DbQuery


class TestDbQuery:
    def testParse(self):
        query_text = """
            SELECT
             'comment' AS type,
             date_added, post.title AS title,
             keyvalue.value || ': ' || comment.body AS body,
             '?Post:' || comment.post_id || '#Comments' AS url
            FROM
             comment
             LEFT JOIN json USING (json_id)
             LEFT JOIN json AS json_content ON (json_content.directory = json.directory AND json_content.file_name='content.json')
             LEFT JOIN keyvalue ON (keyvalue.json_id = json_content.json_id AND key = 'cert_user_id')
             LEFT JOIN post ON (comment.post_id = post.post_id)
            WHERE
             post.date_added > 123
            ORDER BY
             date_added DESC
            LIMIT 20
        """
        query = DbQuery(query_text)
        assert query.parts["LIMIT"] == "20"
        assert query.fields["body"] == "keyvalue.value || ': ' || comment.body"
        assert re.sub("[ \r\n]", "", str(query)) == re.sub("[ \r\n]", "", query_text)
        query.wheres.append("body LIKE '%hello%'")
        assert "body LIKE '%hello%'" in str(query)
