#!/bin/bash

# Script de vérification du déploiement Railway

echo "🔍 VÉRIFICATION DU DÉPLOIEMENT"
echo "================================"
echo ""

URL="https://botanus-production.up.railway.app"

echo "1️⃣ Test page principale..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL/")
if [ "$STATUS" -eq 200 ]; then
    echo "   ✅ Page principale OK (200)"
else
    echo "   ❌ Page principale ERROR ($STATUS)"
fi

echo ""
echo "2️⃣ Test API Stats..."
RESPONSE=$(curl -s "$URL/api/stats")
if echo "$RESPONSE" | grep -q "total"; then
    echo "   ✅ API Stats OK"
    echo "   Réponse: $RESPONSE"
else
    echo "   ❌ API Stats ERROR"
    echo "   Réponse: $RESPONSE"
fi

echo ""
echo "3️⃣ Test API Suggestions..."
RESPONSE=$(curl -s "$URL/api/suggestions")
if echo "$RESPONSE" | grep -q "nom_francais"; then
    echo "   ✅ API Suggestions OK"
else
    echo "   ❌ API Suggestions ERROR"
    echo "   Réponse: $RESPONSE"
fi

echo ""
echo "4️⃣ Test API Library..."
RESPONSE=$(curl -s "$URL/api/library")
if echo "$RESPONSE" | grep -q "plants"; then
    echo "   ✅ API Library OK"
    echo "   Réponse: $RESPONSE"
else
    echo "   ❌ API Library ERROR"
    echo "   Réponse: $RESPONSE"
fi

echo ""
echo "5️⃣ Test API Recherche..."
RESPONSE=$(curl -s "$URL/api/search?q=lavande")
if echo "$RESPONSE" | grep -q "results"; then
    echo "   ✅ API Recherche OK"
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | grep -o '[0-9]*')
    echo "   Résultats trouvés: $COUNT"
else
    echo "   ❌ API Recherche ERROR"
    echo "   Réponse: $RESPONSE"
fi

echo ""
echo "================================"
echo "✅ Vérification terminée"
