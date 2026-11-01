ALTER TABLE customer ADD COLUMN old_email varchar(200);
ALTER TABLE customer RENAME COLUMN old_email TO email;
CREATE TABLE obsolete_import (id bigint PRIMARY KEY);
DROP TABLE obsolete_import;
