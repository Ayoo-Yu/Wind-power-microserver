#!/bin/bash

# Wind Power Microservices Deployment Script
# This script deploys the wind power forecasting microservices platform to Kubernetes

set -e  # Exit on any error

# Configuration
NAMESPACE="wind-power"
DOCKER_REGISTRY="windpower"
IMAGE_TAG="latest"
ENVIRONMENT="development"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed. Please install kubectl first."
        exit 1
    fi

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    # Check if cluster is accessible
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Please ensure your cluster is accessible."
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."

    # Build API Gateway
    log_info "Building API Gateway image..."
    cd ../api-gateway
    docker build -t ${DOCKER_REGISTRY}/api-gateway:${IMAGE_TAG} .
    cd - &> /dev/null

    # Build Tenant Service
    log_info "Building Tenant Service image..."
    cd ../services/tenant-service
    docker build -t ${DOCKER_REGISTRY}/tenant-service:${IMAGE_TAG} .
    cd - &> /dev/null

    # Build SCADA Service
    log_info "Building SCADA Service image..."
    cd ../services/scada-service
    docker build -t ${DOCKER_REGISTRY}/scada-service:${IMAGE_TAG} .
    cd - &> /dev/null

    # Build Meteorological Service
    log_info "Building Meteorological Service image..."
    cd ../services/meteorological-service
    docker build -t ${DOCKER_REGISTRY}/meteorological-service:${IMAGE_TAG} .
    cd - &> /dev/null

    # Build Prediction Service
    log_info "Building Prediction Service image..."
    cd ../services/prediction-service
    docker build -t ${DOCKER_REGISTRY}/prediction-service:${IMAGE_TAG} .
    cd - &> /dev/null

    # Build Reporting Service
    log_info "Building Reporting Service image..."
    cd ../services/reporting-service
    docker build -t ${DOCKER_REGISTRY}/reporting-service:${IMAGE_TAG} .
    cd - &> /dev/null

    log_success "All Docker images built successfully"
}

# Deploy to Kubernetes
deploy_to_kubernetes() {
    log_info "Deploying to Kubernetes..."

    # Create namespace
    log_info "Creating namespace: ${NAMESPACE}"
    kubectl apply -f kubernetes/namespace.yaml

    # Deploy Redis
    log_info "Deploying Redis..."
    kubectl apply -f kubernetes/redis.yaml

    # Wait for Redis to be ready
    log_info "Waiting for Redis to be ready..."
    kubectl wait --for=condition=ready pod -l app=redis -n ${NAMESPACE} --timeout=300s

    # Deploy API Gateway
    log_info "Deploying API Gateway..."
    kubectl apply -f kubernetes/api-gateway.yaml

    # Deploy Tenant Service
    log_info "Deploying Tenant Service..."
    kubectl apply -f kubernetes/tenant-service.yaml

    # Wait for deployments to be ready
    log_info "Waiting for deployments to be ready..."
    kubectl wait --for=condition=ready pod -l app=api-gateway -n ${NAMESPACE} --timeout=600s
    kubectl wait --for=condition=ready pod -l app=tenant-service -n ${NAMESPACE} --timeout=600s

    log_success "Deployment completed successfully"
}

# Check deployment status
check_deployment_status() {
    log_info "Checking deployment status..."

    echo ""
    echo "=== Pod Status ==="
    kubectl get pods -n ${NAMESPACE}

    echo ""
    echo "=== Service Status ==="
    kubectl get services -n ${NAMESPACE}

    echo ""
    echo "=== Ingress Status ==="
    kubectl get ingress -n ${NAMESPACE}

    echo ""
    echo "=== Deployment Status ==="
    kubectl get deployments -n ${NAMESPACE}

    log_success "Deployment status check completed"
}

# Test the deployment
test_deployment() {
    log_info "Testing deployment..."

    # Get API Gateway service endpoint
    API_GATEWAY_URL=$(kubectl get service api-gateway -n ${NAMESPACE} -o jsonpath='{.spec.clusterIP}')

    if [ -z "$API_GATEWAY_URL" ]; then
        log_error "Could not get API Gateway service endpoint"
        return 1
    fi

    log_info "Testing API Gateway health endpoint..."

    # Test health endpoint
    for i in {1..10}; do
        if kubectl run test-pod --image=curlimages/curl --rm -i --restart=Never -- \
           curl -s -o /dev/null -w "%{http_code}" http://${API_GATEWAY_URL}/health; then
            log_success "API Gateway health check passed"
            break
        else
            log_warning "Health check failed, retrying in 10 seconds..."
            sleep 10
        fi
    done

    # Test tenant service through gateway
    log_info "Testing Tenant Service through API Gateway..."

    # This would require a valid JWT token in production
    # For now, we'll just test the service discovery
    kubectl run test-pod --image=curlimages/curl --rm -i --restart=Never -- \
        curl -s http://${API_GATEWAY_URL}/api/services || log_warning "Service discovery test failed"

    log_success "Deployment testing completed"
}

# Show usage information
show_usage() {
    echo "Wind Power Microservices Deployment Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -e, --environment   Set environment (development|staging|production)"
    echo "  -t, --tag          Set Docker image tag"
    echo "  -r, --registry     Set Docker registry"
    echo "  --build-only       Only build Docker images"
    echo "  --deploy-only      Only deploy to Kubernetes"
    echo "  --skip-tests       Skip deployment tests"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Full deployment with default settings"
    echo "  $0 -e production -t v1.0.0          # Deploy to production with specific tag"
    echo "  $0 --build-only                      # Only build Docker images"
    echo "  $0 --deploy-only                     # Only deploy existing images"
}

# Parse command line arguments
BUILD_ONLY=false
DEPLOY_ONLY=false
SKIP_TESTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -r|--registry)
            DOCKER_REGISTRY="$2"
            shift 2
            ;;
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --deploy-only)
            DEPLOY_ONLY=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    log_info "Starting Wind Power Microservices deployment..."
    log_info "Environment: $ENVIRONMENT"
    log_info "Docker Registry: $DOCKER_REGISTRY"
    log_info "Image Tag: $IMAGE_TAG"

    # Check prerequisites
    check_prerequisites

    # Build images if not deploy-only
    if [ "$DEPLOY_ONLY" = false ]; then
        build_images
    fi

    # Deploy to Kubernetes if not build-only
    if [ "$BUILD_ONLY" = false ]; then
        deploy_to_kubernetes
        check_deployment_status

        # Test deployment if not skipped
        if [ "$SKIP_TESTS" = false ]; then
            test_deployment
        fi
    fi

    log_success "Deployment process completed successfully!"
    echo ""
    echo "=== Deployment Summary ==="
    echo "Namespace: $NAMESPACE"
    echo "Environment: $ENVIRONMENT"
    echo "Docker Registry: $DOCKER_REGISTRY"
    echo "Image Tag: $IMAGE_TAG"
    echo ""
    echo "To access the API Gateway:"
    echo "kubectl port-forward svc/api-gateway 8080:80 -n $NAMESPACE"
    echo "curl http://localhost:8080/health"
    echo ""
    echo "For more information, check the logs:"
    echo "kubectl logs -f deployment/api-gateway -n $NAMESPACE"
}

# Run main function
main "$@"