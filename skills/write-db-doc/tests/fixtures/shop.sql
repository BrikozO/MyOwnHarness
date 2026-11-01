-- Deliberately incompatible FK: varchar references integer.
CREATE TABLE `customer` (
    `id` int PRIMARY KEY,
    `name` varchar(100) NOT NULL
) ENGINE=InnoDB;
CREATE TABLE `orders` (
    `id` int PRIMARY KEY,
    `customer_id` varchar(32) NOT NULL,
    `total` decimal(12,2) COMMENT 'Сумма',
    `qty` int NOT NULL,
    FOREIGN KEY (`customer_id`) REFERENCES `customer` (`id`)
) ENGINE=InnoDB;
