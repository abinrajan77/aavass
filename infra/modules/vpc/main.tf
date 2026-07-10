# VPC module — public subnets (ALB, NAT) + private subnets (ECS tasks, RDS) per
# specs/06-cloud-devops.md §1: "RDS and ECS tasks never sit in a public subnet."

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  az_names = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  # Carve /24s out of the supplied /16 (or similar): first N for public, next N for private.
  public_subnet_cidrs  = [for i in range(var.az_count) : cidrsubnet(var.cidr_block, 8, i)]
  private_subnet_cidrs = [for i in range(var.az_count) : cidrsubnet(var.cidr_block, 8, i + var.az_count)]

  nat_gateway_count = var.single_nat_gateway ? 1 : var.az_count

  common_tags = merge(var.tags, {
    Environment = var.env
    ManagedBy   = "terraform"
    Project     = "aavaas"
  })
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-vpc"
  })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-igw"
  })
}

resource "aws_subnet" "public" {
  count                   = var.az_count
  vpc_id                  = aws_vpc.this.id
  cidr_block              = local.public_subnet_cidrs[count.index]
  availability_zone       = local.az_names[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-public-${local.az_names[count.index]}"
    Tier = "public"
  })
}

resource "aws_subnet" "private" {
  count             = var.az_count
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.private_subnet_cidrs[count.index]
  availability_zone = local.az_names[count.index]

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-private-${local.az_names[count.index]}"
    Tier = "private"
  })
}

resource "aws_eip" "nat" {
  count  = local.nat_gateway_count
  domain = "vpc"

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-nat-eip-${count.index}"
  })
}

resource "aws_nat_gateway" "this" {
  count         = local.nat_gateway_count
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-nat-${count.index}"
  })

  depends_on = [aws_internet_gateway.this]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  count          = var.az_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# One private route table per AZ so each can point at its own NAT gateway when
# single_nat_gateway = false; when true, all point at the sole NAT gateway (index 0).
resource "aws_route_table" "private" {
  count  = var.az_count
  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = var.single_nat_gateway ? aws_nat_gateway.this[0].id : aws_nat_gateway.this[count.index].id
  }

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-private-rt-${count.index}"
  })
}

resource "aws_route_table_association" "private" {
  count          = var.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
